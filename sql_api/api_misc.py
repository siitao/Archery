"""
binlog / My2SQL / 查询 / 审计 DRF APIView 集 · 收尾所有剩余旧端点。

覆盖：
  sql/binlog.py          → binlog_list, my2sql
  sql/query.py           → querylog_audit, generate_sql, check_openai
  sql/audit_log.py       → audit_log
  sql/sql_workflow.py    → list_audit, backup_sql, osc_control
  sql/query_privileges.py → applylist, userprivileges, applyforprivileges, modifyprivileges
  sql/instance.py        → schemasync
  sql/views.py           → sqlexport_pre_check (已在 views.py 保留, 不动)
  common/config.py       → change_config (已在 urls.py 保留, 不动)
  common/check.py        → go_inception (已在 urls.py 保留, 不动)

路由：
  POST /api/v1/audit/log/                 — 通用审计日志
  POST /api/v1/audit/sqlworkflow/         — SQL 上线工单审计
  POST /api/v1/audit/querylog/            — 查询日志审计
  POST /api/v1/binlog/list/               — binlog 列表
  POST /api/v1/binlog/my2sql/             — my2sql 解析
  POST /api/v1/query/generate_sql/        — AI 生成 SQL
  GET  /api/v1/query/check_openai/        — 探测 OpenAI
  POST /api/v1/query/applylist/           — 查询权限申请列表
  POST /api/v1/query/userprivileges/      — 用户已有权限
  POST /api/v1/query/applyforprivileges/  — 申请权限
  POST /api/v1/query/modifyprivileges/    — 变更/删除权限
  GET  /api/v1/sqlworkflow/backup_sql/    — 查看回滚 SQL
  POST /api/v1/sqlworkflow/list_audit/    — (旧) SQL 上线审计列表
  POST /api/v1/sqlworkflow/osc_control/   — OSC 进度控制
  POST /api/v1/schemasync/                — SchemaSync 对比
"""
import datetime as _dt
import json as _json
import logging
import os
import time
import traceback
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.db.models import Q, Value as V
from django.db.models.functions import Concat
from django.http import JsonResponse, FileResponse, HttpResponse
from django.db import transaction as _tx
from django_q.tasks import async_task

from common.config import SysConfig
from common.utils.const import WorkflowAction, WorkflowStatus, WorkflowType
from common.utils.extend_json_encoder import encode_json as _encode
from common.utils.timer import FuncTimer
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.views import APIView
from sql.engines import get_engine
from sql.models import (
    ArchiveConfig, ArchiveLog,
    AuditEntry, Instance, QueryLog,
    QueryPrivileges, QueryPrivilegesApply,
    ResourceGroup, SlowQueryHistory, SqlWorkflow,
)
from sql.notify import notify_for_audit
from sql.plugins.my2sql import My2SQL
from sql.plugins.soar import Soar
from sql.services.instance_service import resolve_instance
from sql.utils.resource_group import user_groups, user_instances
from sql.utils.sql_utils import extract_tables, generate_sql
from sql.utils.tasks import task_info
from sql.utils.workflow_audit import Audit, AuditException, get_auditor

logger = logging.getLogger("default")


# ---------- permissions ----------

class AuditUserPermission(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u and u.is_authenticated and (u.is_superuser or u.has_perm("sql.audit_user"))


class QueryApplyListPermission(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u and u.is_authenticated and (u.is_superuser or u.has_perm("sql.menu_queryapplylist"))


class QueryApplyPrivPermission(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u and u.is_authenticated and (u.is_superuser or u.has_perm("sql.query_applypriv"))


class QueryMgtPrivPermission(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u and u.is_authenticated and (u.is_superuser or u.has_perm("sql.query_mgtpriv"))


class SqlWorkflowPermission(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u and u.is_authenticated and (u.is_superuser or u.has_perm("sql.menu_sqlworkflow"))


class SchemasyncPermission(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u and u.is_authenticated and (u.is_superuser or u.has_perm("sql.menu_schemasync"))


# ========== 审计 ==========

class AuditLogView(APIView):
    permission_classes = [IsAuthenticated, AuditUserPermission]

    def post(self, request):
        limit = int(request.data.get("limit", 0))
        offset = int(request.data.get("offset", 0))
        limit = offset + limit
        limit = limit if limit else None
        search = request.data.get("search", "")
        action = request.data.get("action", "")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")

        filter_dict = {}
        if start_date and end_date:
            end_date = _dt.datetime.strptime(end_date, "%Y-%m-%d") + _dt.timedelta(days=1)
            filter_dict["action_time__range"] = (start_date, end_date)
        if action:
            filter_dict["action"] = action

        qs = AuditEntry.objects.filter(**filter_dict)
        if search:
            qs = qs.filter(
                Q(user_name__icontains=search)
                | Q(action__icontains=search)
                | Q(extra_info__icontains=search)
            )

        count = qs.count()
        rows = [row for row in qs.order_by("-action_time")[offset:limit].values(
            "user_id", "user_name", "user_display", "action", "extra_info", "action_time"
        )]
        return JsonResponse(_encode({"total": count, "rows": rows}), safe=False)


class AuditSqlWorkflowView(APIView):
    """SQL 上线工单审计列表（复用旧 sqlworkflow_list_audit 逻辑）。"""
    permission_classes = [IsAuthenticated, AuditUserPermission]

    def post(self, request):
        user = request.user
        nav_status = request.data.get("navStatus")
        instance_id = request.data.get("instance_id")
        group_id = request.data.get("group_id")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")
        limit = int(request.data.get("limit", 0))
        offset = int(request.data.get("offset", 0))
        limit = offset + limit
        limit = limit if limit else None
        search = request.data.get("search")
        syntax_type = request.data.getlist("syntax_type[]")

        filter_dict = {}
        if syntax_type:
            filter_dict["syntax_type__in"] = syntax_type
        if nav_status:
            filter_dict["status"] = nav_status
        if instance_id:
            filter_dict["instance_id"] = instance_id
        if group_id:
            filter_dict["group_id"] = group_id
        if start_date and end_date:
            end_date = _dt.datetime.strptime(end_date, "%Y-%m-%d") + _dt.timedelta(days=1)
            filter_dict["create_time__range"] = (start_date, end_date)

        if user.is_superuser or user.has_perm("sql.audit_user"):
            pass
        elif user.has_perm("sql.sql_review") or user.has_perm("sql.sql_execute_for_resource_group"):
            group_list = user_groups(user)
            group_ids = [g.group_id for g in group_list]
            filter_dict["group_id__in"] = group_ids
        else:
            filter_dict["engineer"] = user.username

        workflow = SqlWorkflow.objects.filter(**filter_dict)
        if search:
            workflow = workflow.filter(
                Q(engineer_display__icontains=search) | Q(workflow_name__icontains=search)
            )

        count = workflow.count()
        rows = [r for r in workflow.order_by("-create_time")[offset:limit].values(
            "id", "workflow_name", "engineer_display", "status", "is_backup",
            "create_time", "instance__instance_name", "db_name", "group_name",
            "syntax_type", "export_format",
        )]
        return JsonResponse(_encode({"total": count, "rows": rows}), safe=False)


class AuditQueryLogView(APIView):
    """查询日志审计列表。"""
    permission_classes = [IsAuthenticated, AuditUserPermission]

    def post(self, request):
        limit = int(request.data.get("limit", 0))
        offset = int(request.data.get("offset", 0))
        limit = offset + limit
        limit = limit if limit else None
        search = request.data.get("search", "")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")

        filter_dict = {}
        if not (request.user.is_superuser or request.user.has_perm("sql.audit_user")):
            filter_dict["username"] = request.user.username
        if start_date and end_date:
            end_date = _dt.datetime.strptime(end_date, "%Y-%m-%d") + _dt.timedelta(days=1)
            filter_dict["create_time__range"] = (start_date, end_date)

        qs = QueryLog.objects.filter(**filter_dict).filter(
            Q(sqllog__icontains=search) if search else Q()
        ).annotate(
            target_instance=F("instance_name"),
            search_db=F("db_name"),
            execute_time=F("query_time"),
            sqllog=V("") if not search else F("sqllog"),
        ) if search else QueryLog.objects.filter(**filter_dict).annotate(
            target_instance=F("instance_name"),
            search_db=F("db_name"),
            execute_time=F("query_time"),
        )
        count = qs.count()
        rows = [r for r in qs.order_by("-create_time")[offset:limit].values(
            "id", "username", "user_display", "target_instance", "search_db",
            "sqllog", "effect_row", "cost_time", "execute_time", "create_time",
        )]
        return JsonResponse(_encode({"total": count, "rows": rows}), safe=False)


# ========== binlog ==========

class BinlogListView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        instance_name = request.data.get("instance_name")
        try:
            instance = resolve_instance(request.user, instance_name=instance_name)
        except Exception:
            return JsonResponse({"status": 1, "msg": "实例不存在或你所在组未关联", "data": []})

        query_engine = get_engine(instance=instance)
        query_result = query_engine.query("information_schema", "show binary logs;")
        if not query_result.error:
            column_list = query_result.column_list
            rows = []
            for row in query_result.rows:
                row_info = {}
                for ri, ri_item in enumerate(row):
                    row_info[column_list[ri]] = ri_item
                rows.append(row_info)
            return JsonResponse({"status": 0, "msg": "ok", "data": rows})
        return JsonResponse({"status": 1, "msg": query_result.error})


class My2sqlView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        instance_name = request.data.get("instance_name")
        rollback = request.data.get("rollback") == "true"
        work_type = "rollback" if rollback else "2sql"
        num = 30 if not request.data.get("num") else int(request.data.get("num"))
        threads = 4 if not request.data.get("threads") else int(request.data.get("threads"))
        start_file = request.data.get("start_file")
        start_pos = request.data.get("start_pos")
        end_file = request.data.get("end_file")
        end_pos = request.data.get("end_pos")
        stop_time = request.data.get("stop_time")
        start_time = request.data.get("start_time")
        only_schemas = request.data.getlist("only_schemas")
        only_tables = request.data.getlist("only_tables[]")
        sql_type = request.data.getlist("sql_type[]")
        extra_info = request.data.get("extra_info") == "true"
        ignore_primary_key = request.data.get("ignore_primary_key") == "true"
        full_columns = request.data.get("full_columns") == "true"
        no_db_prefix = request.data.get("no_db_prefix") == "true"
        file_per_table = request.data.get("file_per_table") == "true"

        if not instance_name:
            return JsonResponse({"status": 1, "msg": "缺少实例名"})

        instance = Instance.objects.get(instance_name=instance_name)
        my2sql = My2SQL()
        username, password = instance.get_username_password()

        # 处理默认值
        if start_pos == "" or start_pos is None:
            start_pos = None
        else:
            start_pos = int(start_pos)
        if end_pos == "" or end_pos is None:
            end_pos = None
        else:
            end_pos = int(end_pos)

        args = {
            "work-type": work_type,
            "host": instance.host,
            "port": instance.port,
            "user": username,
            "password": password,
            "add-extraInfo": extra_info,
            "ignore-primary-key-for-rollback": ignore_primary_key,
            "full-columns": full_columns,
            "no-db-prefix": no_db_prefix,
            "file-per-table": file_per_table,
            "threads": threads,
            "databases": only_schemas,
            "tables": only_tables,
            "sql": sql_type,
            "start-file": start_file,
            "start-pos": start_pos,
            "stop-file": end_file,
            "stop-pos": end_pos,
            "stop-datetime": stop_time,
            "start-datetime": start_time,
            "output-dir": os.path.join(settings.BASE_DIR, "downloads", "my2sql", str(time.time())),
        }
        output_dir = args["output-dir"]
        os.makedirs(output_dir, exist_ok=True)

        cmd_args = my2sql.generate_args2cmd(args)
        try:
            stdout, stderr = my2sql.execute_cmd(cmd_args).communicate()
        except Exception as e:
            logger.error(f"my2sql 执行失败: {traceback.format_exc()}")
            return JsonResponse({"status": 1, "msg": str(e), "data": []})

        if stderr:
            return JsonResponse({"status": 1, "msg": stderr, "data": []})

        # 读取输出文件
        rows = []
        current_extra = ""
        for root, _, files in os.walk(output_dir):
            for fn in sorted(files):
                if not fn.endswith(".sql") or fn.startswith("."):
                    continue
                fp = os.path.join(root, fn)
                with open(fp, encoding="utf-8") as f:
                    for line in f:
                        stripped = line.rstrip("\r\n")
                        content = stripped.lstrip()
                        if content.startswith("#"):
                            current_extra = content
                            continue
                        if content[:6].upper() in ("INSERT", "DELETE", "UPDATE"):
                            sql = content if content.endswith(";") else content + ";"
                            ri = {"sql": sql}
                            if current_extra:
                                ri["extra_info"] = current_extra
                            rows.append(ri)
                            if len(rows) >= num:
                                break
                    if len(rows) >= num:
                        break
            if len(rows) >= num:
                break

        return JsonResponse({"status": 0, "msg": "ok", "data": rows})


# ========== 查询 / AI ==========

class GenerateSqlView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from sql.utils.sql_utils import generate_sql as gs
        text = request.data.get("text", "")
        instance_name = request.data.get("instance_name", "")
        db_name = request.data.get("db_name", "")
        rows = gs(text)
        return JsonResponse({"status": 0, "msg": "ok", "data": rows})


class CheckOpenAIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from common.config import SysConfig
        openai_key = SysConfig().get("openai_key", "")
        return JsonResponse({"status": 0, "msg": "ok", "data": {"openai": bool(openai_key)}})


# ========== 查询权限申请 ==========

def _db_priv(user, instance, db_name):
    return QueryPrivileges.objects.filter(
        user_name=user.username, instance=instance,
        db_name=db_name, priv_type=1, is_deleted=0,
        valid_date__gte=_dt.datetime.now(),
    ).exists()


def _tb_priv(user, instance, db_name, tb_name):
    return QueryPrivileges.objects.filter(
        user_name=user.username, instance=instance,
        db_name=db_name, table_name=tb_name, priv_type=2, is_deleted=0,
        valid_date__gte=_dt.datetime.now(),
    ).exists()


def _query_apply_audit_call_back(apply_id, workflow_status):
    apply_info = QueryPrivilegesApply.objects.get(apply_id=apply_id)
    if workflow_status == WorkflowStatus.PASSED:
        apply_info.status = WorkflowStatus.PASSED
        apply_info.save()
        # 通过后写入权限表
        ins = apply_info.instance
        if apply_info.priv_type == 1:
            for db in apply_info.db_list.split(","):
                QueryPrivileges.objects.update_or_create(
                    user_name=apply_info.user_name,
                    user_display=apply_info.user_display,
                    instance=ins,
                    db_name=db,
                    priv_type=1,
                    defaults={
                        "table_name": "",
                        "limit_num": apply_info.limit_num,
                        "valid_date": apply_info.valid_date,
                        "is_deleted": 0,
                    },
                )
        elif apply_info.priv_type == 2:
            for tb in apply_info.table_list.split(","):
                QueryPrivileges.objects.update_or_create(
                    user_name=apply_info.user_name,
                    user_display=apply_info.user_display,
                    instance=ins,
                    db_name=apply_info.db_list,
                    priv_type=2,
                    defaults={
                        "table_name": tb,
                        "limit_num": apply_info.limit_num,
                        "valid_date": apply_info.valid_date,
                        "is_deleted": 0,
                    },
                )
    elif workflow_status == WorkflowStatus.REJECTED:
        apply_info.status = WorkflowStatus.REJECTED
        apply_info.save()


class QueryApplyListView(APIView):
    permission_classes = [IsAuthenticated, QueryApplyListPermission]

    def post(self, request):
        user = request.user
        limit = int(request.data.get("limit", 0))
        offset = int(request.data.get("offset", 0))
        limit = offset + limit
        search = request.data.get("search", "")

        qs = QueryPrivilegesApply.objects.all()
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(user_display__icontains=search))
        if not user.is_superuser:
            if user.has_perm("sql.query_review"):
                group_ids = [g.group_id for g in user_groups(user)]
                qs = qs.filter(group_id__in=group_ids)
            else:
                qs = qs.filter(user_name=user.username)

        count = qs.count()
        rows = [r for r in qs.order_by("-apply_id")[offset:limit].values(
            "apply_id", "title", "instance__instance_name", "db_list",
            "priv_type", "table_list", "limit_num", "valid_date",
            "user_display", "status", "create_time", "group_name",
        )]
        return JsonResponse(_encode({"total": count, "rows": rows}), safe=False)


class UserPrivilegesView(APIView):
    permission_classes = [IsAuthenticated, QueryApplyListPermission]

    def post(self, request):
        user = request.user
        user_display = request.data.get("user_display", "all")
        limit = int(request.data.get("limit", 0))
        offset = int(request.data.get("offset", 0))
        limit = offset + limit
        search = request.data.get("search", "")

        qs = QueryPrivileges.objects.filter(is_deleted=0, valid_date__gte=_dt.datetime.now())
        if search:
            qs = qs.filter(
                Q(user_display__icontains=search)
                | Q(db_name__icontains=search)
                | Q(table_name__icontains=search)
            )
        if user_display != "all":
            qs = qs.filter(user_display=user_display)
        if not user.is_superuser:
            if user.has_perm("sql.query_mgtpriv"):
                group_ids = [g.group_id for g in user_groups(user)]
                qs = qs.filter(instance__queryprivilegesapply__group_id__in=group_ids)
            else:
                qs = qs.filter(user_name=user.username)

        count = qs.distinct().count()
        rows = [r for r in qs.distinct().order_by("-privilege_id")[offset:limit].values(
            "privilege_id", "user_display", "instance__instance_name",
            "db_name", "priv_type", "table_name", "limit_num", "valid_date",
        )]
        return JsonResponse(_encode({"total": count, "rows": rows}), safe=False)


class ApplyForPrivilegesView(APIView):
    permission_classes = [IsAuthenticated, QueryApplyPrivPermission]

    def post(self, request):
        user = request.user
        title = request.data.get("title")
        instance_name = request.data.get("instance_name")
        group_name = request.data.get("group_name")
        priv_type = request.data.get("priv_type")
        db_name = request.data.get("db_name")
        db_list = request.data.getlist("db_list[]")
        table_list = request.data.getlist("table_list[]")
        valid_date = request.data.get("valid_date")
        limit_num = request.data.get("limit_num")

        result = {"status": 0, "msg": "ok", "data": []}
        if int(priv_type) == 1:
            if not (title and instance_name and db_list and valid_date and limit_num):
                result["status"] = 1
                result["msg"] = "请填写完整"
                return JsonResponse(result)
        elif int(priv_type) == 2:
            if not (title and instance_name and db_name and valid_date and table_list and limit_num):
                result["status"] = 1
                result["msg"] = "请填写完整"
                return JsonResponse(result)

        try:
            user_instances(request.user, tag_codes=["can_read"]).get(instance_name=instance_name)
        except Instance.DoesNotExist:
            return JsonResponse({"status": 1, "msg": "你所在组未关联该实例！"})

        ins = Instance.objects.get(instance_name=instance_name)
        group_id = ResourceGroup.objects.get(group_name=group_name).group_id

        if int(priv_type) == 1:
            for db in db_list:
                if _db_priv(user, ins, db):
                    return JsonResponse({"status": 1, "msg": f"你已拥有{instance_name}实例{db}库权限，不能重复申请"})
        elif int(priv_type) == 2:
            if _db_priv(user, ins, db_name):
                return JsonResponse({"status": 1, "msg": f"你已拥有{instance_name}实例{db_name}库的全部权限，不能重复申请"})
            for tb in table_list:
                if _tb_priv(user, ins, db_name, tb):
                    return JsonResponse({"status": 1, "msg": f"你已拥有{instance_name}实例{db_name}.{tb}表的查询权限，不能重复申请"})

        apply_info = QueryPrivilegesApply(
            title=title, group_id=group_id, group_name=group_name,
            audit_auth_groups="", user_name=user.username, user_display=user.display,
            instance=ins, priv_type=int(priv_type), valid_date=valid_date,
            status=WorkflowStatus.WAITING, limit_num=limit_num,
        )
        if int(priv_type) == 1:
            apply_info.db_list = ",".join(db_list)
            apply_info.table_list = ""
        elif int(priv_type) == 2:
            apply_info.db_list = db_name
            apply_info.table_list = ",".join(table_list)

        audit_handler = get_auditor(workflow=apply_info)
        try:
            with _tx.atomic():
                audit_handler.create_audit()
        except AuditException as e:
            logger.error(f"新建审批流失败, {str(e)}")
            return JsonResponse({"status": 1, "msg": "新建审批流失败, 请联系管理员"})

        _query_apply_audit_call_back(audit_handler.workflow.apply_id, audit_handler.audit.current_status)
        async_task(
            notify_for_audit, workflow_audit=audit_handler.audit, timeout=60,
            task_name=f"query-priv-apply-{audit_handler.workflow.apply_id}",
        )
        return JsonResponse(result)


class ModifyPrivilegesView(APIView):
    permission_classes = [IsAuthenticated, QueryMgtPrivPermission]

    def post(self, request):
        privilege_id = request.data.get("privilege_id")
        type_val = request.data.get("type")
        result = {"status": 0, "msg": "ok", "data": []}

        try:
            priv = QueryPrivileges.objects.get(privilege_id=int(privilege_id))
        except QueryPrivileges.DoesNotExist:
            return JsonResponse({"status": 1, "msg": "待操作权限不存在"})

        if int(type_val) == 1:
            priv.is_deleted = 1
            priv.save(update_fields=["is_deleted"])
        elif int(type_val) == 2:
            valid_date = request.data.get("valid_date")
            limit_num = request.data.get("limit_num")
            priv.valid_date = valid_date
            priv.limit_num = limit_num
            priv.save(update_fields=["valid_date", "limit_num"])
        return JsonResponse(result)


# ========== SQL 上线辅助 ==========

class BackupSqlView(APIView):
    permission_classes = [IsAuthenticated, SqlWorkflowPermission]

    def get(self, request):
        workflow_id = request.GET.get("workflow_id")
        try:
            workflow = SqlWorkflow.objects.get(id=workflow_id)
        except SqlWorkflow.DoesNotExist:
            return JsonResponse({"status": 1, "msg": "工单不存在"})

        query_engine = get_engine(instance=workflow.instance)
        sql_list = query_engine.get_rollback(workflow=workflow)
        rows = []
        if isinstance(sql_list, list):
            rows = []
            for item in sql_list:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    rows.append({"sql": str(item[1]), "label": str(item[0])})
                elif isinstance(item, dict):
                    rows.append(item)
                else:
                    rows.append({"sql": str(item)})
        return JsonResponse({"status": 0, "msg": "ok", "rows": rows})


class OscControlView(APIView):
    permission_classes = [IsAuthenticated, SqlWorkflowPermission]

    def post(self, request):
        workflow_id = request.data.get("workflow_id")
        sqlsha1 = request.data.get("sqlsha1")
        command = request.data.get("command")

        try:
            workflow = SqlWorkflow.objects.get(id=workflow_id)
        except SqlWorkflow.DoesNotExist:
            return JsonResponse({"status": 1, "msg": "工单不存在"})

        engine = get_engine(instance=workflow.instance)
        if command == "get":
            osc_result = engine.get_osc_progress(sqlsha1=sqlsha1)
        elif command == "pause":
            osc_result = engine.pause_osc(sqlsha1=sqlsha1)
        elif command == "resume":
            osc_result = engine.resume_osc(sqlsha1=sqlsha1)
        elif command == "kill":
            osc_result = engine.kill_osc(sqlsha1=sqlsha1)
        else:
            return JsonResponse({"status": 1, "msg": f"未知 command: {command}"})

        if osc_result.error:
            return JsonResponse({"status": 1, "msg": osc_result.error})
        return JsonResponse({"status": 0, "msg": "", "rows": osc_result.to_dict(), "total": len(osc_result.to_dict())})


# ========== SchemaSync ==========

class SchemaSyncView(APIView):
    permission_classes = [IsAuthenticated, SchemasyncPermission]

    def post(self, request):
        instance_name = request.data.get("instance_name")
        db_name = request.data.get("db_name")
        target_instance_name = request.data.get("target_instance_name")
        target_db_name = request.data.get("target_db_name")
        sync_auto_inc = request.data.get("sync_auto_inc") == "true"
        sync_comments = request.data.get("sync_comments") == "true"

        result = {"status": 0, "msg": "ok", "data": {"diff_stdout": "", "patch_stdout": "", "revert_stdout": ""}}

        if db_name == "all" or target_db_name == "all":
            db_name = "*"
            target_db_name = "*"

        instance = Instance.objects.get(instance_name=instance_name)
        target_instance = Instance.objects.get(instance_name=target_instance_name)

        from sql.plugins.schemasync import SchemaSync
        schema_sync = SchemaSync()
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

        args_check = schema_sync.check_args(args)
        if args_check["status"] == 1:
            return JsonResponse(args_check)

        cmd_args = schema_sync.generate_args2cmd(args)
        try:
            stdout, stderr = schema_sync.execute_cmd(cmd_args).communicate()
            diff_stdout = f"{stdout}{stderr}"
        except RuntimeError as e:
            logger.error(f"schemasync 执行命令失败: {e}")
            diff_stdout = "执行对比命令失败，请联系管理员"

        result["data"]["diff_stdout"] = diff_stdout
        return JsonResponse(result)
