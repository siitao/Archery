"""
慢查统计 / SQL 分析 / SQL 优化 DRF APIView 集
替代：sql/slowlog.py (review/review_history)、sql/sql_analyze.py (generate/analyze)

路由：
  POST /api/v1/slowquery/review/          — 慢查统计
  POST /api/v1/slowquery/review_history/  — 慢查明细
  POST /api/v1/sql_analyze/generate/      — 解析上传文件为 SQL 列表
  POST /api/v1/sql_analyze/analyze/       — SOAR 分析 SQL
  POST /api/v1/optimize/sqladvisor/       — SQLAdvisor 建议
  POST /api/v1/optimize/soar/             — SOAR 建议（markdown）
  POST /api/v1/optimize/sqltuning/        — MySQL 调优
  POST /api/v1/optimize/explain/          — 执行计划
"""
import datetime as _dt
import json as _json
import logging
from pathlib import Path

from common.config import SysConfig
from common.utils.extend_json_encoder import ExtendJSONEncoder
from django.db.models import F, Max, Sum, Value as V
from django.db.models.functions import Concat
from django.http import JsonResponse
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.views import APIView
from sql.engines import get_engine
from sql.models import (
    AliyunRdsConfig,
    Instance,
    RedisSlowQuery,
    RedisSlowQueryHistory,
    SlowQuery,
    SlowQueryHistory,
)
from sql.plugins.soar import Soar
from sql.services.instance_service import resolve_instance
from sql.utils.resource_group import user_instances
from sql.utils.sql_utils import generate_sql

logger = logging.getLogger("default")


# ---------- shared ----------

def _encode(data):
    return _json.loads(_json.dumps(data, cls=ExtendJSONEncoder, bigint_as_string=True))


# ---------- permissions ----------

class SlowQueryPermission(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u and u.is_authenticated and (u.is_superuser or u.has_perm("sql.menu_slowquery"))


class SqlAnalyzePermission(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u and u.is_authenticated and (u.is_superuser or u.has_perm("sql.sql_analyze"))


class SqlOptimizePermission(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u and u.is_authenticated and (u.is_superuser or u.has_perm("sql.menu_sqladvisor"))


def _get_and_check_instance(user, instance_name, db_type=None):
    """获取实例并做权限校验。"""
    if not instance_name:
        raise Instance.DoesNotExist
    i = Instance.objects.get(instance_name=instance_name)
    if db_type:
        user_instances(user, db_type=[db_type]).get(instance_name=instance_name)
    else:
        user_instances(user, db_type=[i.db_type]).get(instance_name=instance_name)
    return i


# ========== 慢查统计 ==========

class SlowQueryReviewView(APIView):
    permission_classes = [IsAuthenticated, SlowQueryPermission]

    def post(self, request):
        instance_name = request.data.get("instance_name")
        start_time = request.data.get("StartTime") or "2010-01-01"
        end_time = request.data.get("EndTime") or _dt.datetime.now().strftime("%Y-%m-%d")
        db_name = request.data.get("db_name")
        limit = int(request.data.get("limit") or 0)
        offset = int(request.data.get("offset") or 0)

        try:
            instance_info = _get_and_check_instance(request.user, instance_name)
        except Instance.DoesNotExist:
            return JsonResponse({"status": 1, "msg": "你所在组未关联该实例", "data": []})

        if instance_info.db_type == "redis":
            query_engine = get_engine(instance=instance_info)
            hostnames = query_engine.get_cluster_master_nodes()
            limit = offset + limit
            search = request.data.get("search")
            sortName = str(request.data.get("sortName") or "")
            sortOrder = str(request.data.get("sortOrder") or "").lower()
            end_time = _dt.datetime.strptime(end_time, "%Y-%m-%d") + _dt.timedelta(days=1)
            slowsql_obj = (
                RedisSlowQuery.objects.filter(
                    redisslowqueryhistory__hostname__in=hostnames,
                    redisslowqueryhistory__ts_min__range=(start_time, end_time),
                    fingerprint__icontains=search or "",
                )
                .annotate(SQLText=Max("fingerprint"), SQLId=F("checksum"))
                .values("SQLText", "SQLId")
                .annotate(
                    CreateTime=Max("redisslowqueryhistory__ts_max"),
                    TotalExecutionCounts=Sum("redisslowqueryhistory__cnt"),
                    TotalExecutionTimes=Sum("redisslowqueryhistory__duration_sum"),
                    QueryTimeAvg=Sum("redisslowqueryhistory__duration_sum")
                    / Sum("redisslowqueryhistory__cnt"),
                    DurationPct95=Max("redisslowqueryhistory__duration_pct_95"),
                )
            )
            slow_sql_count = slowsql_obj.count()
            sort = "-" + sortName if sortOrder == "desc" else sortName
            slow_sql_list = slowsql_obj.order_by(sort)[offset:limit]
            sql_slow_log = []
            for r in slow_sql_list:
                avg = r["QueryTimeAvg"]
                r["QueryTimeAvg"] = round(avg, 2) if avg else 0
                t = r["TotalExecutionTimes"]
                r["TotalExecutionTimes"] = round(t / 1000000, 6) if t else 0
                p = r["DurationPct95"]
                r["DurationPct95"] = round(p, 2) if p else 0
                sql_slow_log.append(r)
            result = {"total": slow_sql_count, "rows": sql_slow_log}

        elif AliyunRdsConfig.objects.filter(instance=instance_info, is_enable=True).exists():
            try:
                query_engine = get_engine(instance=instance_info)
                result = query_engine.slowquery_review(start_time, end_time, db_name, limit, offset)
            except Exception as e:
                result = {"status": 1, "msg": f"获取阿里云RDS慢查询失败: {e}", "rows": []}
        else:
            limit = offset + limit
            search = request.data.get("search")
            sortName = str(request.data.get("sortName") or "")
            sortOrder = str(request.data.get("sortOrder") or "").lower()
            end_time = _dt.datetime.strptime(end_time, "%Y-%m-%d") + _dt.timedelta(days=1)
            filter_kwargs = {"slowqueryhistory__db_max": db_name} if db_name else {}
            slowsql_obj = (
                SlowQuery.objects.filter(
                    slowqueryhistory__hostname_max=(
                        instance_info.host + ":" + str(instance_info.port)
                    ),
                    slowqueryhistory__ts_min__range=(start_time, end_time),
                    fingerprint__icontains=search or "",
                    **filter_kwargs,
                )
                .annotate(SQLText=Max("fingerprint"), SQLId=F("checksum"))
                .values("SQLText", "SQLId")
                .annotate(
                    CreateTime=Max("slowqueryhistory__ts_max"),
                    DBName=Max("slowqueryhistory__db_max"),
                    QueryTimeAvg=Sum("slowqueryhistory__query_time_sum") / Sum("slowqueryhistory__ts_cnt"),
                    MySQLTotalExecutionCounts=Sum("slowqueryhistory__ts_cnt"),
                    MySQLTotalExecutionTimes=Sum("slowqueryhistory__query_time_sum"),
                    ParseTotalRowCounts=Sum("slowqueryhistory__rows_examined_sum"),
                    ReturnTotalRowCounts=Sum("slowqueryhistory__rows_sent_sum"),
                    ParseRowAvg=Sum("slowqueryhistory__rows_examined_sum") / Sum("slowqueryhistory__ts_cnt"),
                    ReturnRowAvg=Sum("slowqueryhistory__rows_sent_sum") / Sum("slowqueryhistory__ts_cnt"),
                )
            )
            slow_sql_count = slowsql_obj.count()
            sort = "-" + sortName if sortOrder == "desc" else sortName
            slow_sql_list = slowsql_obj.order_by(sort)[offset:limit]
            sql_slow_log = []
            for r in slow_sql_list:
                r["QueryTimeAvg"] = round(r["QueryTimeAvg"], 6)
                r["MySQLTotalExecutionTimes"] = round(r["MySQLTotalExecutionTimes"], 6)
                r["ParseRowAvg"] = int(r["ParseRowAvg"])
                r["ReturnRowAvg"] = int(r["ReturnRowAvg"])
                sql_slow_log.append(r)
            result = {"total": slow_sql_count, "rows": sql_slow_log}

        return JsonResponse(_encode(result), safe=False)


class SlowQueryReviewHistoryView(APIView):
    permission_classes = [IsAuthenticated, SlowQueryPermission]

    def post(self, request):
        instance_name = request.data.get("instance_name")
        start_time = request.data.get("StartTime") or "2010-01-01"
        end_time = request.data.get("EndTime") or _dt.datetime.now().strftime("%Y-%m-%d")
        db_name = request.data.get("db_name")
        sql_id = request.data.get("SQLId")
        limit = int(request.data.get("limit") or 0)
        offset = int(request.data.get("offset") or 0)

        try:
            instance_info = _get_and_check_instance(request.user, instance_name)
        except Instance.DoesNotExist:
            return JsonResponse({"status": 1, "msg": "你所在组未关联该实例", "data": []})

        if instance_info.db_type == "redis":
            query_engine = get_engine(instance=instance_info)
            hostnames = query_engine.get_cluster_master_nodes()
            search = request.data.get("search")
            sortName = str(request.data.get("sortName") or "")
            sortOrder = str(request.data.get("sortOrder") or "").lower()
            end_time = _dt.datetime.strptime(end_time, "%Y-%m-%d") + _dt.timedelta(days=1)
            limit = offset + limit
            filter_kwargs = {"checksum": sql_id} if sql_id else {}
            slow_sql_record_obj = RedisSlowQueryHistory.objects.filter(
                hostname__in=hostnames,
                ts_min__range=(start_time, end_time),
                sample__icontains=search or "",
                **filter_kwargs,
            ).annotate(
                ExecutionStartTime=F("ts_min"),
                SQLText=F("sample"),
                TotalExecutionCounts=F("cnt"),
                QueryTimePct95=F("duration_pct_95"),
                QueryTimes=F("duration_sum"),
                HostName=F("hostname"),
            )
            count = slow_sql_record_obj.count()
            sort = "-" + sortName if sortOrder == "desc" else sortName
            slow_sql_record_list = slow_sql_record_obj.order_by(sort)[offset:limit].values(
                "ExecutionStartTime", "SQLText", "TotalExecutionCounts",
                "QueryTimePct95", "QueryTimes", "HostName",
            )
            sql_slow_record = []
            for r in slow_sql_record_list:
                p = r["QueryTimePct95"]
                r["QueryTimePct95"] = round(p, 2) if p else 0
                t = r["QueryTimes"]
                r["QueryTimes"] = round(t / 1000000, 6) if t else 0
                sql_slow_record.append(r)
            result = {"total": count, "rows": sql_slow_record}

        elif AliyunRdsConfig.objects.filter(instance=instance_info, is_enable=True).exists():
            try:
                query_engine = get_engine(instance=instance_info)
                result = query_engine.slowquery_review_history(
                    start_time, end_time, db_name, sql_id, limit, offset
                )
            except Exception as e:
                result = {"status": 1, "msg": f"获取阿里云RDS慢查询明细失败: {e}", "rows": []}
        else:
            search = request.data.get("search")
            sortName = str(request.data.get("sortName") or "")
            sortOrder = str(request.data.get("sortOrder") or "").lower()
            end_time = _dt.datetime.strptime(end_time, "%Y-%m-%d") + _dt.timedelta(days=1)
            limit = offset + limit
            filter_kwargs = {}
            if sql_id:
                filter_kwargs["checksum"] = sql_id
            if db_name:
                filter_kwargs["db_max"] = db_name
            slow_sql_record_obj = SlowQueryHistory.objects.filter(
                hostname_max=(instance_info.host + ":" + str(instance_info.port)),
                ts_min__range=(start_time, end_time),
                sample__icontains=search or "",
                **filter_kwargs,
            ).annotate(
                ExecutionStartTime=F("ts_min"),
                DBName=F("db_max"),
                HostAddress=Concat(V("'"), "user_max", V("'"), V("@"), V("'"), "client_max", V("'")),
                SQLText=F("sample"),
                TotalExecutionCounts=F("ts_cnt"),
                QueryTimePct95=F("query_time_pct_95"),
                QueryTimes=F("query_time_sum"),
                LockTimes=F("lock_time_sum"),
                ParseRowCounts=F("rows_examined_sum"),
                ReturnRowCounts=F("rows_sent_sum"),
            )
            count = slow_sql_record_obj.count()
            sort = "-" + sortName if sortOrder == "desc" else sortName
            slow_sql_record_list = slow_sql_record_obj.order_by(sort)[offset:limit].values(
                "ExecutionStartTime", "DBName", "HostAddress", "SQLText",
                "TotalExecutionCounts", "QueryTimePct95", "QueryTimes",
                "LockTimes", "ParseRowCounts", "ReturnRowCounts",
            )
            sql_slow_record = []
            for r in slow_sql_record_list:
                r["QueryTimePct95"] = round(r["QueryTimePct95"], 6)
                r["QueryTimes"] = round(r["QueryTimes"], 6)
                r["LockTimes"] = round(r["LockTimes"], 6)
                sql_slow_record.append(r)
            result = {"total": count, "rows": sql_slow_record}

        return JsonResponse(_encode(result), safe=False)


# ========== SQL 分析 ==========

class SqlAnalyzeGenerateView(APIView):
    permission_classes = [IsAuthenticated, SqlAnalyzePermission]

    def post(self, request):
        text = request.data.get("text")
        if text is None:
            result = {"total": 0, "rows": []}
        else:
            rows = generate_sql(text)
            result = {"total": len(rows), "rows": rows}
        return JsonResponse(_encode(result), safe=False)


class SqlAnalyzeAnalyzeView(APIView):
    permission_classes = [IsAuthenticated, SqlAnalyzePermission]

    def post(self, request):
        text = request.data.get("text")
        instance_name = request.data.get("instance_name")
        db_name = request.data.get("db_name")
        if not text:
            result = {"total": 0, "rows": []}
            return JsonResponse(_encode(result), safe=False)

        soar = Soar()
        online_dsn = ""
        soar_test_dsn = ""
        if instance_name and db_name:
            try:
                instance = _get_and_check_instance(request.user, instance_name, db_type="mysql")
            except Instance.DoesNotExist:
                return JsonResponse({"status": 1, "msg": "你所在组未关联该实例！", "data": []})
            soar_test_dsn = SysConfig().get("soar_test_dsn") or ""
            user, password = instance.get_username_password()
            online_dsn = f"{user}:{password}@{instance.host}:{instance.port}/{db_name}"

        args = {
            "report-type": "markdown",
            "query": "",
            "online-dsn": online_dsn,
            "test-dsn": soar_test_dsn,
            "allow-online-as-test": False,
        }
        rows = generate_sql(text)
        for row in rows:
            try:
                p = Path(row["sql"].strip())
                if p.exists():
                    return JsonResponse({"status": 1, "msg": "SQL 语句不合法", "data": []})
            except OSError:
                pass
            args["query"] = row["sql"]
            cmd_args = soar.generate_args2cmd(args=args)
            stdout, stderr = soar.execute_cmd(cmd_args).communicate()
            row["report"] = stdout if stdout else stderr

        result = {"total": len(rows), "rows": rows}
        return JsonResponse(_encode(result), safe=False)


# ========== SQL 优化 ==========

class OptimizeSqlAdvisorView(APIView):
    permission_classes = [IsAuthenticated, SqlOptimizePermission]

    def post(self, request):
        instance_name = request.data.get("instance_name")
        db_name = request.data.get("db_name")
        sql_content = request.data.get("sql_content")
        verbose = request.data.get("verbose", 1)
        engine = get_engine(instance=instance_name)
        dsn = engine.get_connection().dsn
        res = Soar().soar_analyze(sql_content, dsn, verbose)
        return JsonResponse({"status": 0, "msg": "", "data": res})


class OptimizeSoarView(APIView):
    permission_classes = [IsAuthenticated, SqlOptimizePermission]

    def post(self, request):
        instance_name = request.data.get("instance_name")
        db_name = request.data.get("db_name")
        sql_content = request.data.get("sql")
        engine = get_engine(instance=instance_name)
        dsn = engine.get_connection().dsn
        res = Soar().soar_analyze(sql_content, dsn)
        return JsonResponse({"status": 0, "msg": "", "data": res})


class OptimizeSqlTuningView(APIView):
    permission_classes = [IsAuthenticated, SqlOptimizePermission]

    def post(self, request):
        instance_name = request.data.get("instance_name")
        db_name = request.data.get("db_name")
        sql_content = request.data.get("sql_content")
        engine = get_engine(instance=instance_name)
        dsn = engine.get_connection().dsn
        res = Soar().sql_tuning(sql_content, dsn)
        return JsonResponse({"status": 0, "msg": "", "data": res})


class ExplainSqlView(APIView):
    permission_classes = [IsAuthenticated, SqlOptimizePermission]

    def post(self, request):
        instance_name = request.data.get("instance_name")
        db_name = request.data.get("db_name")
        sql_content = request.data.get("sql_content")
        engine = get_engine(instance=instance_name)
        dsn = engine.get_connection().dsn
        explain = engine.explain_sql(sql_content, dsn)
        return JsonResponse({"status": 0, "msg": "", "data": explain})
