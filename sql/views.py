# -*- coding: UTF-8 -*-
"""Phase 4 精简后的 views.py · 仅保留 SPA 未完全取代的渲染视图与 JSON API。"""
import os
import traceback

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import Group
from django.http import (
    HttpResponseRedirect,
    FileResponse,
    JsonResponse,
)
from django.shortcuts import render, get_object_or_404
from django.conf import settings

from common.config import SysConfig
from common.utils.permission import superuser_required
from sql.engines import get_engine
from sql.offlinedownload import OffLineDownLoad
from sql.utils.resource_group import user_instances
from sql.utils.sql_review import can_rollback

from .models import (
    SqlWorkflow,
    ResourceGroup,
    Config,
    InstanceTag,
    Instance,
    TwoFactorAuthConfig,
)

import logging

logger = logging.getLogger("default")


# ---------- 根/登录/2FA ----------

def index(request):
    index_path_url = SysConfig().get("index_path_url", "sqlworkflow")
    return HttpResponseRedirect(f"/{index_path_url.strip('/')}/")


def login(request):
    """登录页面（保留 SSO 入口：OIDC/DingTalk/CAS）"""
    if request.user and request.user.is_authenticated:
        return HttpResponseRedirect("/")

    return render(
        request,
        "login.html",
        context={
            "sign_up_enabled": SysConfig().get("sign_up_enabled"),
            "oidc_enabled": settings.ENABLE_OIDC,
            "dingding_enabled": settings.ENABLE_DINGDING,
            "cas_enabled": settings.ENABLE_CAS,
            "oidc_btn_name": SysConfig().get("oidc_btn_name", "以OIDC登录"),
        },
    )


def twofa(request):
    """2FA 认证页面（SSO 流程可能跳转）"""
    if request.user.is_authenticated:
        return HttpResponseRedirect("/")

    username = request.session.get("user")
    if username:
        verify_mode = request.session.get("verify_mode")
        twofa_enabled = TwoFactorAuthConfig.objects.filter(username=username)
        user_auth_types = [twofa.auth_type for twofa in twofa_enabled]

        auth_types = []
        for user_auth_type in user_auth_types:
            auth_type = {}
            auth_type["code"] = user_auth_type
            if user_auth_type == "totp":
                auth_type["display"] = "Google身份验证器"
            elif user_auth_type == "sms":
                auth_type["display"] = "短信验证码"
            auth_types.append(auth_type)
        if "sms" in user_auth_types:
            phone = TwoFactorAuthConfig.objects.get(
                username=username, auth_type="sms"
            ).phone
        else:
            phone = 0
    else:
        return HttpResponseRedirect("/login/")

    return render(
        request,
        "2fa.html",
        context={
            "verify_mode": verify_mode,
            "auth_types": auth_types,
            "username": username,
            "phone": phone,
        },
    )


# ---------- 待办 ----------

def workflows(request):
    """待办列表页面（SPA header 仍跳 /workflow/）"""
    return render(request, "workflow.html")


# ---------- 配置管理（后备） ----------

@superuser_required
def config(request):
    """配置管理页面"""
    group_list = ResourceGroup.objects.all()
    auth_group_list = Group.objects.all()
    instance_tags = InstanceTag.objects.all()
    db_type = ["mysql", "oracle", "mongo", "clickhouse", "redis", "doris", "tdengine"]
    all_config = Config.objects.all().values("item", "value")
    sys_config = {}
    for items in all_config:
        sys_config[items["item"]] = items["value"]

    if not sys_config.get("default_chat_model", ""):
        sys_config["default_chat_model"] = "gpt-3.5-turbo"
    if not sys_config.get("default_query_template", ""):
        sys_config["default_query_template"] = (
            "你是一个熟悉 {{db_type}} 的工程师, "
            "我会给你一些基本信息和要求, 你会生成一个查询语句给我使用, "
            "不要返回任何注释和序号, 仅返回查询语句："
            "{{table_schema}} \n {{user_input}}"
        )

    from common.utils.const import WorkflowType

    context = {
        "group_list": group_list,
        "auth_group_list": auth_group_list,
        "instance_tags": instance_tags,
        "db_type": db_type,
        "config": sys_config,
        "workflow_choices": WorkflowType,
    }
    return render(request, "config.html", context)


# ---------- 回滚 · 文件下载 ----------

def rollback_download(request):
    """
    下载工单的回滚 SQL 文件（GET /rollback/?workflow_id=X&download=true）。
    原 views.rollback() 的文件下载分支，剥离渲染部分后保留。
    """
    workflow_id = request.GET.get("workflow_id")
    if not can_rollback(request.user, workflow_id):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    if not workflow_id:
        return render(request, "error.html", {"errMsg": "workflow_id参数为空."})

    workflow = get_object_or_404(SqlWorkflow, id=int(workflow_id))

    try:
        query_engine = get_engine(instance=workflow.instance)
        list_backup_sql = query_engine.get_rollback(workflow=workflow)
    except Exception as msg:
        logger.error(traceback.format_exc())
        return render(request, "error.html", {"errMsg": msg})

    path = os.path.join(settings.BASE_DIR, "downloads/rollback")
    os.makedirs(path, exist_ok=True)
    file_name = f"{path}/rollback_{workflow_id}.sql"
    with open(file_name, "w") as f:
        for sql in list_backup_sql:
            f.write(f"/*{sql[0]}*/\n{sql[1]}\n")

    response = FileResponse(open(file_name, "rb"))
    response["Content-Type"] = "application/octet-stream"
    response["Content-Disposition"] = (
        f'attachment;filename="rollback_{workflow_id}.sql"'
    )
    return response


# ---------- 数据导出预检（JSON API） ----------

@permission_required("sql.sqlexport_submit", raise_exception=True)
def sqlexport_pre_check(request):
    """数据导出提交前预检，按各引擎查询规则校验并统计导出行数。"""
    result = {"status": 0, "msg": "ok", "data": {}}
    instance_name = request.POST.get("instance_name")
    db_name = request.POST.get("db_name")
    sql_content = request.POST.get("sql_content")

    if not instance_name or not db_name or not sql_content:
        result["status"] = 1
        result["msg"] = "页面提交参数可能为空"
        return JsonResponse(result)

    try:
        instance = user_instances(request.user, tag_codes=["can_read"]).get(
            instance_name=instance_name
        )
    except Instance.DoesNotExist:
        result["status"] = 1
        result["msg"] = "你所在组未关联该实例"
        return JsonResponse(result)

    instance.sql_content = sql_content
    instance.selected_db_name = db_name
    check_result = OffLineDownLoad().pre_count_check(workflow=instance)
    result["data"] = {
        "error_count": check_result.error_count,
        "warning_count": check_result.warning_count,
        "rows": check_result.to_dict(),
    }
    if check_result.error_count:
        result["status"] = 1
        result["msg"] = check_result.rows[0].errormessage if check_result.rows else ""
    return JsonResponse(result)
