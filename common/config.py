# -*- coding: UTF-8 -*-
import logging
import traceback

import simplejson as json
from django.http import HttpResponse

from common.utils.permission import superuser_required
from sql.models import Config
from django.db import transaction

logger = logging.getLogger("default")


class SysConfig(object):
    def __init__(self):
        self.sys_config = {}

    def get_all_config(self):
        try:
            # 获取系统配置信息
            all_config = Config.objects.all().values("item", "value")
            sys_config = {}
            for items in all_config:
                if items["value"] in ("true", "True"):
                    items["value"] = True
                elif items["value"] in ("false", "False"):
                    items["value"] = False
                sys_config[items["item"]] = items["value"]
            self.sys_config = sys_config
        except Exception as m:
            logger.error(f"获取系统配置信息失败:{m}{traceback.format_exc()}")
            self.sys_config = {}

    def get(self, key, default_value=None):
        value = self.sys_config.get(key)
        if value:
            return value
        # 尝试去数据库里取
        config_entry = Config.objects.filter(item=key).last()
        if config_entry:
            # 清洗成 python 的 bool
            value = self.filter_bool(config_entry.value)
        # 是字符串的话, 如果是空, 或者全是空格, 返回默认值
        if isinstance(value, str) and value.strip() == "":
            return default_value
        if value is not None:
            self.sys_config[key] = value
            return value
        return default_value

    @staticmethod
    def filter_bool(value: str):
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        return value

    def set(self, key, value):
        if value is True:
            db_value = "true"
        elif value is False:
            db_value = "false"
        else:
            db_value = value
        obj, created = Config.objects.update_or_create(
            item=key, defaults={"value": db_value}
        )
        self.sys_config.update({key: value})

    def replace(self, configs):
        result = {"status": 0, "msg": "ok", "data": []}
        # 清空并替换
        try:
            with transaction.atomic():
                self.purge()
                Config.objects.bulk_create(
                    [
                        Config(
                            item=items["key"].strip(), value=str(items["value"]).strip()
                        )
                        for items in json.loads(configs)
                    ]
                )
        except Exception as e:
            logger.error(traceback.format_exc())
            result["status"] = 1
            result["msg"] = str(e)
        finally:
            self.get_all_config()
        return result

    def purge(self):
        """清除所有配置, 供测试以及replace方法使用"""
        try:
            with transaction.atomic():
                Config.objects.all().delete()
                self.sys_config = {}
        except Exception as m:
            logger.error(f"删除缓存失败:{m}{traceback.format_exc()}")

    # ---------- 认证方式配置 ----------
    # 认证相关 key 白名单（与 .env 变量名对齐，便于回写）。
    # auth_provider 取值: "local" | "ldap" | "oidc" | "dingding" | "cas"
    AUTH_PROVIDER_KEYS = {
        "common": ("auth_provider", "oidc_btn_name"),
        "ldap": (
            "auth_ldap_server_uri",
            "auth_ldap_bind_dn",
            "auth_ldap_bind_password",
            "auth_ldap_user_dn_template",
            "auth_ldap_user_search_base",
            "auth_ldap_user_search_filter",
            "auth_ldap_user_attr_map",
        ),
        "oidc": (
            "oidc_rp_wellknown_url",
            "oidc_rp_client_id",
            "oidc_rp_client_secret",
            "oidc_rp_scopes",
            "oidc_rp_sign_algo",
            "oidc_user_attr_map",
            "oidc_btn_name",
        ),
        "dingding": (
            "ding_app_key",
            "ding_app_secret",
            "ding_callback_url",
        ),
        "cas": (
            "cas_server_url",
            "cas_version",
            "cas_verify_ssl_certificate",
        ),
    }

    def get_auth_provider(self):
        """当前外部认证方式（local/ldap/oidc/dingding/cas）。

        未配置时回退到 None（由调用方再回退到 settings.ENABLE_*）。
        """
        provider = self.get("auth_provider")
        if provider in ("ldap", "oidc", "dingding", "cas"):
            return provider
        return None  # "local" 或其它值视为未启用外部认证

    def get_auth_config(self):
        """返回全部认证相关 key-value 字典（含各方式参数）。"""
        all_keys = set()
        for keys in self.AUTH_PROVIDER_KEYS.values():
            all_keys.update(keys)
        result = {}
        for key in all_keys:
            # 拿不到时给空串，便于前端回填表单
            result[key] = self.get(key, "")
        # auth_provider 缺省 local
        result["auth_provider"] = self.get("auth_provider", "local")
        return result

    def set_auth_config(self, provider, params):
        """保存认证配置（单点写 DB，不触发 reload）。

        provider: "local" | "ldap" | "oidc" | "dingding" | "cas"
        params: dict, 仅本方式相关 key
        """
        self.set("auth_provider", provider)
        # 仅写当前方式相关的 key，避免污染其它方式的历史值
        allowed = set(self.AUTH_PROVIDER_KEYS.get(provider, ()))
        for key, value in params.items():
            if key in allowed:
                # password/secret 类敏感值若前端传空串则跳过（保留旧值）
                if value == "" and key in (
                    "auth_ldap_bind_password",
                    "oidc_rp_client_secret",
                    "ding_app_secret",
                ):
                    continue
                self.set(key, value)
        return self.get_auth_config()


# 修改系统配置
@superuser_required
def change_config(request):
    configs = request.POST.get("configs")
    archer_config = SysConfig()
    result = archer_config.replace(configs)
    # 返回结果
    return HttpResponse(json.dumps(result), content_type="application/json")
