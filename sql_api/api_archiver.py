"""数据归档（PTArchiver）的 SPA 接口：归档详情（JSON）+ 审核（JSON）。

旧的 ``sql/archiver.py`` 里 6 个 /archive/* 接口（list/apply/log/switch/once/audit）在迁移期
继续供 SPA 调用；唯独审核接口 ``archive_audit`` 成功后 302 跳详情页、失败 render error.html，
对 SPA（XHR）不友好。这里补两个 JSON 接口供 SPA 使用，不动旧的。详情页所需 review_info /
can_review / logs 也由这里一次性返回（复刻 ``views.archive_detail``）。
"""

import logging

from django.db import transaction
from django_q.tasks import async_task
from drf_spectacular.utils import extend_schema
from rest_framework import views, permissions
from rest_framework.response import Response

from common.utils.const import WorkflowAction, WorkflowStatus, WorkflowType
from sql.models import ArchiveConfig
from sql.notify import notify_for_audit
from sql.utils.resource_group import user_groups
from sql.utils.workflow_audit import (
    Audit,
    AuditException,
    AuditV2,
    get_auditor,
)

logger = logging.getLogger("default")


def _serialize_review_info(review_info):
    """ReviewInfo.nodes → 可 JSON 序列化的列表。"""
    nodes = []
    for n in review_info.nodes:
        nodes.append(
            {
                "group_name": n.group.name if n.group else "自动通过",
                "is_current_node": n.is_current_node,
                "is_passed_node": n.is_passed_node,
                "is_auto_pass": n.is_auto_pass,
            }
        )
    return nodes


def _archive_config_dict(cfg: ArchiveConfig) -> dict:
    return {
        "id": cfg.id,
        "title": cfg.title,
        "group_name": cfg.resource_group.group_name,
        "src_instance_name": cfg.src_instance.instance_name if cfg.src_instance else "",
        "src_db_name": cfg.src_db_name,
        "src_table_name": cfg.src_table_name,
        "dest_instance_name": cfg.dest_instance.instance_name if cfg.dest_instance else "",
        "dest_db_name": cfg.dest_db_name or "",
        "dest_table_name": cfg.dest_table_name or "",
        "mode": cfg.mode,
        "no_delete": cfg.no_delete,
        "sleep": cfg.sleep,
        "condition": cfg.condition,
        "status": cfg.status,
        "state": cfg.state,
        "user_display": cfg.user_display,
        "create_time": cfg.create_time,
    }


class ArchiveDetail(views.APIView):
    """归档配置详情（含审批流 / 是否可审核 / 当前审核人 / 审核日志）。"""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="归档配置详情",
        description="返回归档配置、审批流节点、当前审核人、是否可审核、审核日志，供 SPA 详情页渲染。",
    )
    def get(self, request, pk):
        archive_config = ArchiveConfig.objects.get(pk=pk)
        audit_handler = AuditV2(
            workflow=archive_config, resource_group=archive_config.resource_group
        )
        review_info = audit_handler.get_review_info()

        # 是否可审核（复刻 archive_detail：can_operate(PASS) 不抛异常即可审核）
        try:
            audit_handler.can_operate(WorkflowAction.PASS, request.user)
            can_review = True
        except AuditException:
            can_review = False

        # 审核日志
        logs = []
        last_operation_info = ""
        try:
            audit = Audit.detail_by_workflow_id(
                workflow_id=pk, workflow_type=WorkflowType.ARCHIVE
            )
            log_qs = Audit.logs(audit_id=audit.audit_id).values(
                "operation_type_desc",
                "operation_info",
                "operator_display",
                "operation_time",
            )
            logs = [row for row in log_qs]
            if logs:
                last_operation_info = logs[-1]["operation_info"] or ""
        except Exception as e:  # noqa: BLE001
            logger.debug(f"归档配置 {pk} 无审核日志: {e}")

        # 当前审核人
        current_reviewers = []
        for node in review_info.nodes:
            if not node.is_current_node:
                continue
            for user in node.group.user_set.filter(is_active=1):
                group_names = [g.group_name for g in user_groups(user)]
                if archive_config.resource_group.group_name in group_names:
                    current_reviewers.append(
                        {"username": user.username, "display": user.display or user.username}
                    )

        return Response(
            {
                "archive": _archive_config_dict(archive_config),
                "review_info": _serialize_review_info(review_info),
                "current_reviewers": current_reviewers,
                "can_review": can_review,
                "last_operation_info": last_operation_info,
                "logs": logs,
            }
        )


class ArchiveAudit(views.APIView):
    """归档审核（JSON 版，替代旧的 302 ``archive_audit``）。

    audit_status: 1 通过 / 2 驳回（WorkflowAction.PASS / REJECT）。
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="归档审核",
        description="通过 / 驳回归档申请，返回 JSON {status,msg}（不再 302）。需 sql.archive_review 权限。",
    )
    def post(self, request):
        result = {"status": 0, "msg": "ok"}
        try:
            archive_id = int(request.data["archive_id"])
            audit_status = WorkflowAction(int(request.data["audit_status"]))
        except (KeyError, ValueError, TypeError) as e:
            result["status"] = 1
            result["msg"] = f"参数错误: {e}"
            return Response(result)

        audit_remark = request.data.get("audit_remark") or ""

        try:
            archive_workflow = ArchiveConfig.objects.get(id=archive_id)
        except ArchiveConfig.DoesNotExist:
            result["status"] = 1
            result["msg"] = "工单不存在"
            return Response(result)

        resource_group = archive_workflow.resource_group
        auditor = get_auditor(workflow=archive_workflow, resource_group=resource_group)

        # 权限兜底：无权操作则 can_operate 抛 AuditException
        try:
            with transaction.atomic():
                workflow_audit_detail = auditor.operate(
                    audit_status, request.user, audit_remark
                )
                auditor.workflow.status = auditor.audit.current_status
                if auditor.audit.current_status == WorkflowStatus.PASSED:
                    auditor.workflow.state = True
                auditor.workflow.save()
        except AuditException as e:
            result["status"] = 1
            result["msg"] = f"审核失败: {e}"
            return Response(result)

        async_task(
            notify_for_audit,
            workflow_audit=auditor.audit,
            workflow_audit_detail=workflow_audit_detail,
            timeout=60,
            task_name=f"archive-audit-{archive_id}",
        )
        return Response(result)
