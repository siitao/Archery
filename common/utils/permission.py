# -*- coding: UTF-8 -*-
"""权限校验装饰器。

越权时统一返回 JSON 响应（SPA 友好）。不再渲染 error.html，
后端业务模板已全部退役（Phase 5）。
"""
import simplejson as json
from django.http import HttpResponse


def _deny(msg="您无权操作，请联系管理员"):
    result = {"status": 1, "msg": msg, "data": []}
    return HttpResponse(json.dumps(result), content_type="application/json")


# 管理员操作权限验证
def superuser_required(func):
    def wrapper(request, *args, **kw):
        if request.user.is_superuser is False:
            return _deny()
        return func(request, *args, **kw)

    return wrapper


# 角色操作权限验证
def role_required(roles=()):
    def _deco(func):
        def wrapper(request, *args, **kw):
            user = request.user
            if user.role not in roles and user.is_superuser is False:
                return _deny()
            return func(request, *args, **kw)

        return wrapper

    return _deco
