# -*- coding: UTF-8 -*-
"""Phase 4 收尾后的 sql/urls.py · 仅保留 login/workflow/config/rollback/download/schemasync/sqlexport_pre_check + jsi18n。
   所有旧 JSON 端点已迁至 sql_api/urls.py。"""

from django.urls import path
from django.views.i18n import JavaScriptCatalog

from common import auth, config, check
from sql import views, instance, offlinedownload

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

    # ---- 回滚 · 文件下载 + 离线下载 + 数据导出预检 ----
    path("rollback/", views.rollback_download),
    path("downloadfile/", offlinedownload.offline_file_download),
    path("sqlexport/pre_check/", views.sqlexport_pre_check),

    # ---- SchemaSync（仍用旧端点，待 SPA 切到 /api/v1/schemasync/） ----
    path("instance/schemasync/", instance.schemasync),

    # ---- Django 内部 ----
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
]
