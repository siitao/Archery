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
from . import api_user, api_instance, api_workflow, api_sqlquery, api_document, api_query_priv, api_archiver, api_dashboard, api_slowlog

router = routers.DefaultRouter()

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
    path("info", views.info),
    path("debug", views.debug),
    path("do_once/mirage", views.mirage),
]
