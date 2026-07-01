# -*- coding: UTF-8 -*-

import logging
import os
import time

import simplejson as json
from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from django.views.decorators.cache import cache_page

from common.utils.extend_json_encoder import ExtendJSONEncoder
from common.utils.convert import Convert
from sql.engines import get_engine
from sql.services.resource_service import list_instance_resources
from sql.plugins.schemasync import SchemaSync
from sql.utils.sql_utils import filter_db_list
from .models import Instance, ParamTemplate

logger = logging.getLogger("default")


@permission_required("sql.menu_instance_list", raise_exception=True)
def lists(request):
    """获取实例列表"""
    limit = int(request.POST.get("limit"))
    offset = int(request.POST.get("offset"))
    type = request.POST.get("type")
    db_type = request.POST.get("db_type")
    tags = request.POST.getlist("tags[]")
    limit = offset + limit
    search = request.POST.get("search", "")
    sortName = str(request.POST.get("sortName"))
    sortOrder = str(request.POST.get("sortOrder")).lower()

    # 组合筛选项
    filter_dict = dict()
    # 过滤搜索
    if search:
        filter_dict["instance_name__icontains"] = search
    # 过滤实例类型
    if type:
        filter_dict["type"] = type
    # 过滤数据库类型
    if db_type:
        filter_dict["db_type"] = db_type

    instances = Instance.objects.filter(**filter_dict)
    # 过滤标签，返回同时包含全部标签的实例，TODO 循环会生成多表JOIN，如果数据量大会存在效率问题
    if tags:
        for tag in tags:
            instances = instances.filter(instance_tag=tag, instance_tag__active=True)

    count = instances.count()
    if sortName == "instance_name":
        instances = instances.order_by(getattr(Convert(sortName, "gbk"), sortOrder)())[
            offset:limit
        ]
    else:
        instances = instances.order_by(
            "-" + sortName if sortOrder == "desc" else sortName
        )[offset:limit]
    instances = instances.values(
        "id", "instance_name", "db_type", "type", "host", "port", "user"
    )

    # QuerySet 序列化
    rows = [row for row in instances]

    result = {"total": count, "rows": rows}
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


@permission_required("sql.menu_schemasync", raise_exception=True)
def schemasync(request):
    """对比实例schema信息"""
    instance_name = request.POST.get("instance_name")
    db_name = request.POST.get("db_name")
    target_instance_name = request.POST.get("target_instance_name")
    target_db_name = request.POST.get("target_db_name")
    sync_auto_inc = True if request.POST.get("sync_auto_inc") == "true" else False
    sync_comments = True if request.POST.get("sync_comments") == "true" else False
    result = {
        "status": 0,
        "msg": "ok",
        "data": {"diff_stdout": "", "patch_stdout": "", "revert_stdout": ""},
    }

    # 循环对比全部数据库
    if db_name == "all" or target_db_name == "all":
        db_name = "*"
        target_db_name = "*"

    # 取出该实例的连接方式
    instance = Instance.objects.get(instance_name=instance_name)
    target_instance = Instance.objects.get(instance_name=target_instance_name)

    # 提交给SchemaSync获取对比结果
    schema_sync = SchemaSync()
    # 准备参数
    tag = int(time.time())
    output_directory = os.path.join(settings.BASE_DIR, "downloads/schemasync/")
    os.makedirs(output_directory, exist_ok=True)

    username, password = instance.get_username_password()
    target_username, target_password = target_instance.get_username_password()

    args = {
        "sync-auto-inc": sync_auto_inc,
        "sync-comments": sync_comments,
        "charset": "utf8mb4",
        "tag": tag,
        "output-directory": output_directory,
        "source": f"mysql://{username}:{password}@{instance.host}:{instance.port}/{db_name}",
        "target": f"mysql://{target_username}:{target_password}@{target_instance.host}:{target_instance.port}/{target_db_name}",
    }
    # 参数检查
    args_check_result = schema_sync.check_args(args)
    if args_check_result["status"] == 1:
        return HttpResponse(
            json.dumps(args_check_result), content_type="application/json"
        )
    # 参数转换
    cmd_args = schema_sync.generate_args2cmd(args)
    # 执行命令
    try:
        stdout, stderr = schema_sync.execute_cmd(cmd_args).communicate()
        diff_stdout = f"{stdout}{stderr}"
    except RuntimeError as e:
        logger.error(f"schemasync执行命令失败，异常详情：{e}")
        diff_stdout = "执行对比命令失败，请联系管理员"

    # 非全部数据库对比可以读取对比结果并在前端展示
    if db_name != "*":
        date = time.strftime("%Y%m%d", time.localtime())
        patch_sql_file = "%s%s_%s.%s.patch.sql" % (
            output_directory,
            target_db_name,
            tag,
            date,
        )
        revert_sql_file = "%s%s_%s.%s.revert.sql" % (
            output_directory,
            target_db_name,
            tag,
            date,
        )
        try:
            with open(patch_sql_file, "r") as f:
                patch_sql = f.read()
        except FileNotFoundError as e:
            logger.error(f"schemasync读取patch文件失败，异常详情：{e}")
            patch_sql = "读取对比结果文件失败，请联系管理员"
        try:
            with open(revert_sql_file, "r") as f:
                revert_sql = f.read()
        except FileNotFoundError as e:
            logger.error(f"schemasync读取revert文件失败，异常详情：{e}")
            revert_sql = "读取对比结果文件失败，请联系管理员"
        result["data"] = {
            "diff_stdout": diff_stdout,
            "patch_stdout": patch_sql,
            "revert_stdout": revert_sql,
        }
    else:
        result["data"] = {
            "diff_stdout": diff_stdout,
            "patch_stdout": "",
            "revert_stdout": "",
        }

    return HttpResponse(json.dumps(result), content_type="application/json")


@cache_page(60 * 5, key_prefix="insRes")
def instance_resource(request):
    """
    获取实例内的资源信息，database、schema、table、column
    :param request:
    :return:
    """
    result = list_instance_resources(
        user=request.user,
        resource_type=request.GET.get("resource_type"),
        instance_id=request.GET.get("instance_id"),
        instance_name=request.GET.get("instance_name"),
        db_name=request.GET.get("db_name", ""),
        schema_name=request.GET.get("schema_name", ""),
        tb_name=request.GET.get("tb_name", ""),
    )
    return HttpResponse(json.dumps(result), content_type="application/json")
