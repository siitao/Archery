"""慢查询历史趋势数据（JSON）。

旧版 ``sql/slowlog.py:report`` 返回 pyecharts ``render_embed()`` 的 HTML，无法在 Vue 渲染。
这里复用同样的 ChartDao 查询，返回结构化数据，供前端 echarts 绘制双 series 折线
（慢查次数 + 慢查时长 95%）。支持 MySQL 与 Redis 实例。
"""

import logging

import pymysql
from drf_spectacular.utils import extend_schema
from rest_framework import views, permissions
from rest_framework.response import Response

from common.utils.chart_dao import ChartDao
from sql.engines import get_engine
from sql.models import Instance

logger = logging.getLogger("default")


class SlowQueryTrend(views.APIView):
    """慢查询历史趋势（按日：慢查次数 + 慢查时长 95%）。"""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="慢查询历史趋势",
        description="按 checksum 返回慢查询历史趋势（按日：慢查次数 + 慢查时长95%），供 echarts 渲染。",
    )
    def get(self, request):
        checksum = request.GET.get("checksum", "").strip()
        instance_name = request.GET.get("instance_name", "").strip()
        if not checksum:
            return Response({"error": "checksum 不能为空"}, status=400)
        checksum = pymysql.escape_string(checksum)

        is_redis = False
        hostnames = None
        if instance_name:
            try:
                instance_info = Instance.objects.get(instance_name=instance_name)
                is_redis = instance_info.db_type == "redis"
                if is_redis:
                    hostnames = get_engine(instance=instance_info).get_cluster_master_nodes()
            except Instance.DoesNotExist:
                pass

        if is_redis and hostnames:
            cnt_data = ChartDao().redis_slow_query_review_history_by_cnt(checksum, hostnames)
            pct_data = ChartDao().redis_slow_query_review_history_by_pct_95_time(checksum, hostnames)
        else:
            cnt_data = ChartDao().slow_query_review_history_by_cnt(checksum)
            pct_data = ChartDao().slow_query_review_history_by_pct_95_time(checksum)

        # cnt 行: (sum_ts_cnt, date)；pct 行: (pct95_time, date)
        # 以 cnt 的日期为横轴，pct 按日期对齐（缺日补 null）
        x = [row[1] for row in cnt_data["rows"]]
        count = [int(row[0]) for row in cnt_data["rows"]]
        pct_map = {row[1]: str(row[0]) for row in pct_data["rows"]}
        pct95 = [pct_map.get(day, "") for day in x]

        return Response({"x": x, "series": [{"name": "慢查次数", "data": count}, {"name": "慢查时长(95%)", "data": pct95}]})
