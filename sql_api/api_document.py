"""相关文档：把静态 Markdown 文档以纯文本形式交给前端渲染。"""

import os

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import views
from rest_framework.response import Response

from .permissions import IsDocumentPageUser


class DbAprinciplesDocument(views.APIView):
    """MySQL 设计规范文档（docs/docs.md）。

    旧版 ``sql/views.py:dbaprinciples`` 把 Markdown 嵌进模板里的 JS 字符串
    （故 ``\\n`` 转义），改走 DRF 后 JSON 自带转义，直接返回原文即可，
    由前端用 markdown 渲染器展示。
    """

    permission_classes = [IsDocumentPageUser]

    @extend_schema(
        summary="相关文档（MySQL 设计规范）",
        description="返回 docs/docs.md 的原始 Markdown 文本，供前端 markdown 渲染器展示。",
    )
    def get(self, request):
        file_path = os.path.join(settings.BASE_DIR, "docs", "docs.md")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return Response({"title": "MySQL 数据库设计规范", "content": content})
