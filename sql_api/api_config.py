"""系统配置项管理。

旧版 POST /config/change/（common.config.change_config）已有，接受 [{key,value}] JSON。
这里补一个 GET 端点，供 SPA 加载当前全部配置值（superuser 专用）。
"""

import logging

from django.http import JsonResponse
from drf_spectacular.utils import extend_schema
from rest_framework import views, permissions
from rest_framework.response import Response

from common.config import SysConfig
from common.utils.openai import test_openai_connection

logger = logging.getLogger(__name__)


class IsSuperuser(permissions.BasePermission):
    """仅超管。"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class ConfigView(views.APIView):
    """系统全部配置（GET → {key:value} 字典；POST 仍走旧 /config/change/）。"""

    permission_classes = [IsSuperuser]

    @extend_schema(
        summary="系统配置（全部）",
        description="返回全部配置项 key-value 字典（superuser 专用）。POST 保存仍走旧 /config/change/。",
    )
    def get(self, request):
        sys_config = SysConfig()
        sys_config.get_all_config()
        return Response(sys_config.sys_config)


class CheckAIConnectionView(views.APIView):
    """AI 服务连接测试。

    接收表单参数（允许测试尚未保存的临时值），发送一个最简 chat 请求验证连通性。
    """

    permission_classes = [IsSuperuser]

    @extend_schema(
        summary="AI 服务连接测试",
        description="测试 openai_base_url / openai_api_key / default_chat_model 是否可用，"
        "发送一个最简 chat 请求验证连通性。",
    )
    def post(self, request):
        data = request.data
        base_url = data.get("openai_base_url")
        api_key = data.get("openai_api_key")
        model = data.get("default_chat_model")
        ok, msg = test_openai_connection(base_url=base_url, api_key=api_key, model=model)
        return JsonResponse(
            {"status": 0 if ok else 1, "msg": "连接成功" if ok else f"连接失败：{msg}"}
        )
