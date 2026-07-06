# -*- coding: UTF-8 -*-
"""Phase 5 收尾后的 views.py · 仅保留 SPA 尚未取代的渲染视图。

A 档已迁移到 DRF（sql_api/）的端点：
  - rollback_download       → /api/v1/rollback/ (api_misc.RollbackDownloadView)
  - sqlexport_pre_check     → /api/v1/sqlexport/pre_check/ (api_misc.SqlexportPreCheckView)

保留的渲染页（B 档再迁 SPA）：
  - index        根路径重定向
  - login/twofa  登录 + 2FA（SSO 入口）
  - config       配置管理（超管，后备页）
"""
import logging

from django.contrib.auth.models import Group
from django.http import HttpResponseRedirect
from django.shortcuts import render

from common.config import SysConfig
from common.utils.permission import superuser_required

from .models import (
    ResourceGroup,
    Config,
    InstanceTag,
    TwoFactorAuthConfig,
)

logger = logging.getLogger("default")


# ---------- 根/登录/2FA ----------

def index(request):
    index_path_url = SysConfig().get("index_path_url", "sqlworkflow")
    return HttpResponseRedirect(f"/{index_path_url.strip('/')}/")


def login(request):
    """登录页面（保留 SSO 入口：OIDC/DingTalk/CAS）"""
    if request.user and request.user.is_authenticated:
        return HttpResponseRedirect("/")

    # 外部认证方式：优先取数据库 auth_provider；未配置时回退到 settings.ENABLE_*
    auth_provider = SysConfig().get("auth_provider")
    if auth_provider in ("ldap", "oidc", "dingding", "cas"):
        oidc_enabled = auth_provider == "oidc"
        dingding_enabled = auth_provider == "dingding"
        cas_enabled = auth_provider == "cas"
    else:
        # 兼容旧的 .env 启动配置
        from django.conf import settings

        oidc_enabled = getattr(settings, "ENABLE_OIDC", False)
        dingding_enabled = getattr(settings, "ENABLE_DINGDING", False)
        cas_enabled = getattr(settings, "ENABLE_CAS", False)

    return render(
        request,
        "login.html",
        context={
            "sign_up_enabled": SysConfig().get("sign_up_enabled"),
            "oidc_enabled": oidc_enabled,
            "dingding_enabled": dingding_enabled,
            "cas_enabled": cas_enabled,
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
