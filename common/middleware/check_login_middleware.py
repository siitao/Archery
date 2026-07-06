# -*- coding: UTF-8 -*-
"""登录态校验中间件。

策略（SPA 友好）：
- DRF 路由（/api/v1/、/api/auth/）整体放行，交给 DRF 自身鉴权返回 401。
- 对未登录请求分两类响应：
  - XHR / 接受 JSON 的 API 请求 → 返回 401 JSON {detail: 未登录}，供 SPA axios 拦截器统一处理；
  - 浏览器导航（HTML 页面） → 维持 302 重定向到 /login/（如直接访问 /admin/）。
"""
import re

from django.http import JsonResponse, HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin

IGNORE_URL = [
    "/login/",
    "/login/2fa/",
    "/api/info",
    "/oidc/callback/",
    "/oidc/authenticate/",
    "/oidc/logout/",
    "/dingding/callback/",
    "/dingding/authenticate/",
    "/cas/authenticate/",
]

IGNORE_URL_RE = r"/api/(v1|auth)/\w+"


def _wants_json(request):
    """请求是否期望 JSON 响应（XHR 或 Accept 含 application/json）。"""
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return True
    accept = request.headers.get("accept", "")
    return "application/json" in accept and "text/html" not in accept


class CheckLoginMiddleware(MiddlewareMixin):
    @staticmethod
    def process_request(request):
        """未登录时：API 请求返回 401 JSON；页面请求重定向到 /login/。"""
        if not request.user.is_authenticated:
            # 白名单（登录页、SSO 回调等）整体放行
            if (
                request.path in IGNORE_URL
                or re.match(IGNORE_URL_RE, request.path) is not None
                or (
                    re.match(r"/user/qrcode/\w+", request.path)
                    and request.session.get("user")
                )
            ):
                return None

            if _wants_json(request):
                return JsonResponse({"detail": "未登录或会话已过期"}, status=401)
            return HttpResponseRedirect("/login/")
