from django.urls import path, include
from sql_api import views
from rest_framework import routers
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from . import api_user, api_instance, api_workflow, api_sqlquery, api_document, api_query_priv, api_archiver, api_dashboard, api_slowlog, api_config, api_dictionary, api_instance_admin, api_diagnostic

router = routers.DefaultRouter()
router.register(
    "dictionary",
    api_dictionary.DataDictionaryViewSet,
    basename="dictionary",
)

urlpatterns = [
    path("v1/", include(router.urls)),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "swagger/",
        SpectacularSwaggerView.as_view(url_name="sql_api:schema"),
        name="swagger",
    ),
    path(
        "redoc/", SpectacularRedocView.as_view(url_name="sql_api:schema"), name="redoc"
    ),
    path("v1/user/", api_user.UserList.as_view()),
    path("v1/user/<int:pk>/", api_user.UserDetail.as_view()),
    path("v1/user/me/", api_user.CurrentUser.as_view()),
    path("v1/user/group/", api_user.GroupList.as_view()),
    path("v1/user/permissions/", api_user.PermissionList.as_view()),
    path("v1/user/group/<int:pk>/", api_user.GroupDetail.as_view()),
    path("v1/user/resourcegroup/", api_user.ResourceGroupList.as_view()),
    path("v1/user/resourcegroup/<int:pk>/", api_user.ResourceGroupDetail.as_view()),
    path("v1/user/auth/", api_user.UserAuth.as_view()),
    path("v1/user/2fa/", api_user.TwoFA.as_view()),
    path("v1/user/2fa/context/", api_user.TwoFAVerifyContext.as_view()),
    path("v1/user/2fa/state/", api_user.TwoFAState.as_view()),
    path("v1/user/2fa/save/", api_user.TwoFASave.as_view()),
    path("v1/user/2fa/verify/", api_user.TwoFAVerify.as_view()),
    path("v1/instance/", api_instance.InstanceList.as_view()),
    path("v1/instance/tags/", api_instance.InstanceTagList.as_view()),
    path("v1/instance/<int:pk>/", api_instance.InstanceDetail.as_view()),
    path("v1/instance/resource/", api_instance.InstanceResource.as_view()),
    path("v1/instance/table-instances/", api_instance.TableInstanceLookup.as_view()),
    path("v1/sqlquery/instances/", api_sqlquery.SQLQueryInstancesView.as_view()),
    path("v1/sqlquery/resources/", api_sqlquery.SQLQueryResourcesView.as_view()),
    path(
        "v1/sqlquery/describetable/", api_sqlquery.SQLQueryDescribeTableView.as_view()
    ),
    path("v1/sqlquery/execute/", api_sqlquery.SQLQueryExecuteView.as_view()),
    path("v1/sqlquery/logs/", api_sqlquery.SQLQueryLogsView.as_view()),
    path("v1/sqlquery/favorites/", api_sqlquery.SQLQueryFavoritesView.as_view()),
    path("v1/instance/tunnel/", api_instance.TunnelList.as_view()),
    path("v1/instance/rds/", api_instance.AliyunRdsList.as_view()),
    path(
        "v1/instance/rds/by_instance/",
        api_instance.AliyunRdsByInstance.as_view(),
    ),
    path("v1/instance/rds/<int:pk>/", api_instance.AliyunRdsDetail.as_view()),
    path("v1/workflow/", api_workflow.WorkflowList.as_view()),
    path("v1/workflow/sqlcheck/", api_workflow.ExecuteCheck.as_view()),
    path("v1/workflow/audit/", api_workflow.AuditWorkflow.as_view()),
    path("v1/workflow/auditlist/", api_workflow.WorkflowAuditList.as_view()),
    path("v1/workflow/execute/", api_workflow.ExecuteWorkflow.as_view()),
    path("v1/workflow/log/", api_workflow.WorkflowLogList.as_view()),
    path("v1/workflow/timingtask/", api_workflow.TimingTask.as_view()),
    path("v1/workflow/alter_run_date/", api_workflow.AlterRunDate.as_view()),
    path("v1/workflow/<int:workflow_id>/", api_workflow.WorkflowDetail.as_view()),
    path(
        "v1/document/dbaprinciples/",
        api_document.DbAprinciplesDocument.as_view(),
    ),
    path(
        "v1/query_priv/<int:apply_id>/",
        api_query_priv.QueryPrivApplyDetail.as_view(),
    ),
    path("v1/query_priv/audit/", api_query_priv.QueryPrivAudit.as_view()),
    path("v1/archive/<int:pk>/", api_archiver.ArchiveDetail.as_view()),
    path("v1/archive/audit/", api_archiver.ArchiveAudit.as_view()),
    path(
        "v1/dashboard/charts/",
        api_dashboard.DashboardCharts.as_view(),
    ),
    path(
        "v1/slowquery/trend/",
        api_slowlog.SlowQueryTrend.as_view(),
    ),
    path("v1/config/", api_config.ConfigView.as_view()),
    # ---- 实例管理 ----
    path("v1/instance/accounts/", api_instance_admin.AccountListView.as_view()),
    path("v1/instance/accounts/create/", api_instance_admin.AccountCreateView.as_view()),
    path("v1/instance/accounts/edit/", api_instance_admin.AccountEditView.as_view()),
    path("v1/instance/accounts/grant/", api_instance_admin.AccountGrantView.as_view()),
    path("v1/instance/accounts/reset_pwd/", api_instance_admin.AccountResetPwdView.as_view()),
    path("v1/instance/accounts/lock/", api_instance_admin.AccountLockView.as_view()),
    path("v1/instance/accounts/delete/", api_instance_admin.AccountDeleteView.as_view()),
    path("v1/instance/databases/", api_instance_admin.DatabaseListView.as_view()),
    path("v1/instance/databases/create/", api_instance_admin.DatabaseCreateView.as_view()),
    path("v1/instance/databases/edit/", api_instance_admin.DatabaseEditView.as_view()),
    path("v1/instance/params/", api_instance_admin.ParamListView.as_view()),
    path("v1/instance/params/history/", api_instance_admin.ParamHistoryView.as_view()),
    path("v1/instance/params/edit/", api_instance_admin.ParamEditView.as_view()),
    path("v1/instance/params/compare/", api_instance_admin.ParamCompareView.as_view()),
    # ---- 会话诊断 ----
    path("v1/diagnostic/process/", api_diagnostic.ProcessView.as_view()),
    path("v1/diagnostic/create_kill/", api_diagnostic.CreateKillSessionView.as_view()),
    path("v1/diagnostic/kill/", api_diagnostic.KillSessionView.as_view()),
    path("v1/diagnostic/tablespace/", api_diagnostic.TableSpaceView.as_view()),
    path("v1/diagnostic/trxandlocks/", api_diagnostic.TrxAndLocksView.as_view()),
    path("v1/diagnostic/innodb_trx/", api_diagnostic.InnodbTrxView.as_view()),
    path("info", views.info),
    path("debug", views.debug),
    path("do_once/mirage", views.mirage),
]
