# -*- coding: UTF-8 -*-

from django.urls import path
from django.views.i18n import JavaScriptCatalog

import sql.query_privileges
import sql.sql_optimize
from common import auth, config, check
from sql import (
    views,
    sql_workflow,
    sql_analyze,
    query,
    slowlog,
    instance,
    db_diagnostic,
    resource_group,
    binlog,
    archiver,
    audit_log,
    offlinedownload,
)

urlpatterns = [
    # ---- 根/登录/2FA（保留） ----
    path("", views.index),
    path("index/", views.index),
    path("login/", views.login, name="login"),
    path("login/2fa/", views.twofa, name="twofa"),
    path("logout/", auth.sign_out),
    path("authenticate/", auth.authenticate_entry),

    # ---- 待办列表（SPA header 仍跳 /workflow/） ----
    path("workflow/", views.workflows),

    # ---- 配置管理（保留后备） ----
    path("config/", views.config),
    path("config/change/", config.change_config),
    path("check/go_inception/", check.go_inception),

    # ---- 回滚 · 文件下载（SPA 调用） ----
    path("rollback/", views.rollback_download),
    path("downloadfile/", offlinedownload.offline_file_download),

    # ---- SQL 上线 JSON（SPA 仍在调用） ----
    path("sqlworkflow_list_audit/", sql_workflow.sql_workflow_list_audit),
    path("sqlworkflow/backup_sql/", sql_workflow.backup_sql),
    path("inception/osc_control/", sql_workflow.osc_control),

    # ---- SQL 分析 / 优化 ----
    path("sql_analyze/generate/", sql_analyze.generate),
    path("sql_analyze/analyze/", sql_analyze.analyze),
    path("query/explain/", sql.sql_optimize.explain),
    path(
        "slowquery/optimize_sqladvisor/", sql.sql_optimize.optimize_sqladvisor
    ),
    path(
        "slowquery/optimize_sqltuning/", sql.sql_optimize.optimize_sqltuning
    ),
    path("slowquery/optimize_soar/", sql.sql_optimize.optimize_soar),

    # ---- 慢查 JSON ----
    path("slowquery/review/", slowlog.slowquery_review),
    path("slowquery/review_history/", slowlog.slowquery_review_history),

    # ---- 查询 / 审计 ----
    path("query/querylog_audit/", query.querylog_audit),
    path("query/generate_sql/", query.generate_sql),
    path("check/openai/", query.check_openai),
    path("query/applylist/", sql.query_privileges.query_priv_apply_list),
    path("query/userprivileges/", sql.query_privileges.user_query_priv),
    path(
        "query/applyforprivileges/", sql.query_privileges.query_priv_apply
    ),
    path(
        "query/modifyprivileges/", sql.query_privileges.query_priv_modify
    ),
    path("audit/log/", audit_log.audit_log),

    # ---- 实例管理 JSON（已迁至 /api/v1/instance/accounts/、/databases/、/params/） ----
    path("instance/schemasync/", instance.schemasync),

    # ---- 会话诊断 ----
    path("db_diagnostic/process/", db_diagnostic.process),
    path(
        "db_diagnostic/create_kill_session/",
        db_diagnostic.create_kill_session,
    ),
    path("db_diagnostic/kill_session/", db_diagnostic.kill_session),
    path("db_diagnostic/tablespace/", db_diagnostic.tablespace),
    path("db_diagnostic/trxandlocks/", db_diagnostic.trxandlocks),
    path("db_diagnostic/innodb_trx/", db_diagnostic.innodb_trx),

    # ---- 实例参数（已迁至 /api/v1/instance/params/） ----


    # ---- 归档 JSON ----
    path("archive/list/", archiver.archive_list),
    path("archive/apply/", archiver.archive_apply),
    path("archive/switch/", archiver.archive_switch),
    path("archive/once/", archiver.archive_once),
    path("archive/log/", archiver.archive_log),

    # ---- binlog ----
    path("binlog/list/", binlog.binlog_list),
    path("binlog/my2sql/", binlog.my2sql),
    path("binlog/del_log/", binlog.del_binlog),

    # ---- 资源组 JSON ----
    path("group/addrelation/", resource_group.addrelation),
    path("group/removerelation/", resource_group.removerelation),
    path("group/relations/", resource_group.associated_objects),
    path("group/instances/", resource_group.instances),
    path("group/unassociated/", resource_group.unassociated_objects),
    path("group/auditors/", resource_group.auditors),
    path("group/changeauditors/", resource_group.changeauditors),

    # ---- 数据导出预检 ----
    path("sqlexport/pre_check/", views.sqlexport_pre_check),

    # ---- Django 内部 ----
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
]
