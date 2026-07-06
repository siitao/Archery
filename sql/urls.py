# -*- coding: UTF-8 -*-
"""Phase 5 收尾后的 sql/urls.py · 仅保留 SPA 尚未取代的渲染视图 + jsi18n。

A 档迁移已完成的端点（全部搬到 sql_api/urls.py，走 /api/v1/）：
  - authenticate / logout        → /api/v1/authenticate/、/api/v1/logout/
  - config/change、check/go_inception → /api/v1/config/change/、/api/v1/config/check_inception/
  - rollback、downloadfile、sqlexport/pre_check → /api/v1/rollback/、/api/v1/downloadfile/、/api/v1/sqlexport/pre_check/
  - instance/schemasync          → /api/v1/schemasync/

保留：
  - login/2fa/config 渲染页（B 档再处理）
  - jsi18n（Django 内部，admin 用）
"""

from django.urls import path
from django.views.i18n import JavaScriptCatalog

from sql import views

urlpatterns = [
    # ---- 根/登录/2FA（渲染页，B 档再迁 SPA） ----
    path("", views.index),
    path("index/", views.index),
    path("login/", views.login, name="login"),
    path("login/2fa/", views.twofa, name="twofa"),

    # ---- 配置管理（渲染页，B 档再迁 SPA） ----
    path("config/", views.config),

    # ---- Django 内部 ----
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
]
