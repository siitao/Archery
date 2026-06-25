"""Dashboard 图表数据（JSON）。

旧版 ``common/dashboard.py:DashboardApi`` 返回 pyecharts ``render_embed()`` 的 HTML/JS 片段，
无法直接在 Vue/echarts 渲染。这里直接复用 ``ChartDao`` 的原始行数据，返回结构化 JSON，
供前端用 echarts 自行绘制。日期范围必传（默认由前端给近 30 天）。
"""

import datetime
import logging

from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import views, permissions
from rest_framework.response import Response

from common.utils.chart_dao import ChartDao

logger = logging.getLogger("default")


def _validate_date(date_str):
    """校验 YYYY-MM-DD，非法抛 ValueError。"""
    return datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")


def _pairs(rows):
    """[(label, value), ...] → [{name, value}]（pie/bar 通用）。"""
    return [{"name": str(r[0]), "value": r[1]} for r in rows]


class DashboardCharts(views.APIView):
    """Dashboard 10 张图表的原始数据（echarts 友好）。"""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Dashboard 图表数据",
        description="返回 SQL 上线/查询/慢查等 10 张图表的原始数据，供前端 echarts 渲染。",
    )
    def get(self, request):
        start_date_str = request.GET.get("start_date")
        end_date_str = request.GET.get("end_date")
        try:
            start_date = _validate_date(start_date_str)
            end_date = _validate_date(end_date_str)
        except (ValueError, TypeError):
            return Response({"error": "日期有误，格式需为 YYYY-MM-DD"}, status=400)

        chart_dao = ChartDao()

        # 日期序列（bar1 / line1 横轴对齐用）
        date_list = chart_dao.get_date_list(
            datetime.datetime.strptime(start_date, "%Y-%m-%d"),
            datetime.datetime.strptime(end_date, "%Y-%m-%d"),
        )

        def by_date(dao_rows):
            """{date: count} → 按 date_list 对齐的值数组（缺日补 0）。"""
            d = {row[0]: row[1] for row in dao_rows}
            return [d.get(day, 0) for day in date_list]

        # bar1 SQL 上线数量（按日）
        bar1 = {
            "x": date_list,
            "series": [{"name": "SQL 上线数量", "data": by_date(chart_dao.workflow_by_date(start_date, end_date)["rows"])}],
        }
        # pie1 SQL 上线统计（按组）
        pie1 = _pairs(chart_dao.workflow_by_group(start_date, end_date)["rows"])
        # pie2 SQL 语法类型
        pie2 = _pairs(chart_dao.syntax_type(start_date, end_date)["rows"])
        # bar2 SQL 上线用户
        bar2_data = chart_dao.workflow_by_user(start_date, end_date)["rows"]
        bar2 = {"x": [r[0] for r in bar2_data], "series": [{"name": "工单数", "data": [r[1] for r in bar2_data]}]}
        # line1 SQL 查询统计（检索行数 + 检索次数，按日双 series）
        line1 = {
            "x": date_list,
            "series": [
                {"name": "检索行数", "data": by_date(chart_dao.querylog_effect_row_by_date(start_date, end_date)["rows"])},
                {"name": "检索次数", "data": by_date(chart_dao.querylog_count_by_date(start_date, end_date)["rows"])},
            ],
        }
        # pie4 SQL 查询用户（检索行数）
        pie4 = _pairs(chart_dao.querylog_effect_row_by_user(start_date, end_date)["rows"])
        # pie5 DB 检索行数
        pie5 = _pairs(chart_dao.querylog_effect_row_by_db(start_date, end_date)["rows"])
        # pie3 慢查询 db/user 维度
        pie3 = _pairs(chart_dao.slow_query_count_by_db_by_user()["rows"])
        # bar3 慢查询 db 维度
        bar3_data = chart_dao.slow_query_count_by_db()["rows"]
        bar3 = {"x": [r[0] for r in bar3_data], "series": [{"name": "慢查数", "data": [r[1] for r in bar3_data]}]}
        # bar5 SQL 上线工单
        bar5_data = chart_dao.query_sql_prod_bill(start_date, end_date)["rows"]
        bar5 = {"x": [r[0] for r in bar5_data], "series": [{"name": "工单数", "data": [r[1] for r in bar5_data]}]}

        return Response(
            {
                "bar1": bar1,
                "bar2": bar2,
                "bar3": bar3,
                "bar5": bar5,
                "pie1": pie1,
                "pie2": pie2,
                "pie3": pie3,
                "pie4": pie4,
                "pie5": pie5,
                "line1": line1,
            }
        )
