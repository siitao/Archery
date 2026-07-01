"""系统配置项管理。

旧版 POST /config/change/（common.config.change_config）已有，接受 [{key,value}] JSON。
这里补一个 GET 端点，供 SPA 加载当前全部配置值（superuser 专用）。
"""

import logging

from drf_spectacular.utils import extend_schema
from rest_framework import views, permissions
from rest_framework.response import Response

from common.config import SysConfig

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
