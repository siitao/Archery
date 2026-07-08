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
import re
from pathlib import Path

import sqlparse
from common.config import SysConfig
from common.utils.extend_json_encoder import encode_json as _encode
from common.utils.openai import OpenaiClient, check_openai_config
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
from sql.plugins.sqladvisor import SQLAdvisor
from sql.services.instance_service import resolve_instance
from sql.sql_tuning import SqlTuning
from sql.utils.resource_group import user_instances
from sql.utils.sql_utils import extract_tables, generate_sql

logger = logging.getLogger("default")


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


def _apply_sort(qs, request, default=None):
    """根据 sortName/sortOrder 对 QuerySet 排序。

    前端未传排序参数（空字符串）时回退到 default；字段非法时降级为 default，
    再不行就不排序，避免 Django 抛 FieldError 导致整个接口 500。

    注意：不能用 ``a or b or qs`` 这种写法 —— 对 QuerySet 求布尔值会触发一次
    查询并缓存结果，导致后续切片/链式调用（如 ``.values()``）失效。所以这里
    一律用显式 return。
    """
    sort_name = str(request.data.get("sortName") or "").strip()
    sort_order = str(request.data.get("sortOrder") or "").lower()
    if not sort_name:
        sort_name = (default or "").lstrip("-")

    def _try(prefix, name):
        if not name:
            return None
        try:
            return qs.order_by(prefix + name)
        except Exception:
            logger.warning("慢查排序字段无效: %s%s", prefix, name, exc_info=True)
            return None

    prefix = "-" if sort_order == "desc" else ""

    # 不能用 a or b or qs：对 QuerySet 求布尔值会触发查询并缓存 _result_cache，
    # 使后续 [offset:limit] 切片返回 list、.values() 失效
    # （'list' object has no attribute 'values'）。必须用 is not None 判断。
    ordered = _try(prefix, sort_name)
    if ordered is not None:
        return ordered
    if default:
        ordered = _try("", default.lstrip("-"))
        if ordered is not None:
            return ordered
    return qs


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
            slow_sql_list = _apply_sort(
                slowsql_obj, request, default="-TotalExecutionCounts"
            )[offset:limit]
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
            slow_sql_list = _apply_sort(
                slowsql_obj, request, default="-MySQLTotalExecutionCounts"
            )[offset:limit]
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
            slow_sql_record_list = (
                _apply_sort(slow_sql_record_obj, request, default="-ExecutionStartTime")[
                    offset:limit
                ].values(
                    "ExecutionStartTime", "SQLText", "TotalExecutionCounts",
                    "QueryTimePct95", "QueryTimes", "HostName",
                )
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
            slow_sql_record_list = (
                _apply_sort(slow_sql_record_obj, request, default="-ExecutionStartTime")[
                    offset:limit
                ].values(
                    "ExecutionStartTime", "DBName", "HostAddress", "SQLText",
                    "TotalExecutionCounts", "QueryTimePct95", "QueryTimes",
                    "LockTimes", "ParseRowCounts", "ReturnRowCounts",
                )
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
    """SQLAdvisor 索引优化建议"""

    permission_classes = [IsAuthenticated, SqlOptimizePermission]

    def post(self, request):
        sql_content = request.data.get("sql_content")
        instance_name = request.data.get("instance_name")
        db_name = request.data.get("db_name")
        verbose = request.data.get("verbose", 1)
        result = {"status": 0, "msg": "ok", "data": []}

        # 服务器端参数验证
        if not sql_content or not instance_name:
            result["status"] = 1
            result["msg"] = "页面提交参数可能为空"
            return JsonResponse(result)

        # 实例权限校验（限 mysql）
        try:
            instance = _get_and_check_instance(
                request.user, instance_name, db_type="mysql"
            )
        except Instance.DoesNotExist:
            result["status"] = 1
            result["msg"] = "你所在组未关联该实例！"
            return JsonResponse(result)

        # 检查 sqladvisor 程序路径
        if not SysConfig().get("sqladvisor"):
            result["status"] = 1
            result["msg"] = "请配置SQLAdvisor路径！"
            return JsonResponse(result)

        # 提交给 sqladvisor 获取分析报告
        sqladvisor = SQLAdvisor()
        args = {
            "h": instance.host,
            "P": instance.port,
            "u": instance.user,
            "p": instance.password,
            "d": db_name,
            "v": verbose,
            "q": sql_content.strip(),
        }
        args_check_result = sqladvisor.check_args(args)
        if args_check_result["status"] == 1:
            return JsonResponse(args_check_result)
        cmd_args = sqladvisor.generate_args2cmd(args)
        try:
            stdout, stderr = sqladvisor.execute_cmd(cmd_args).communicate()
            result["data"] = f"{stdout}{stderr}"
        except RuntimeError as e:
            result["status"] = 1
            result["msg"] = str(e)
        return JsonResponse(result)


class OptimizeSoarView(APIView):
    """SOAR 优化建议（markdown 报告）"""

    permission_classes = [IsAuthenticated, SqlOptimizePermission]

    def post(self, request):
        instance_name = request.data.get("instance_name")
        db_name = request.data.get("db_name")
        sql = request.data.get("sql")
        result = {"status": 0, "msg": "ok", "data": []}

        # 服务器端参数验证
        if not (instance_name and db_name and sql):
            result["status"] = 1
            result["msg"] = "页面提交参数可能为空"
            return JsonResponse(result)

        # 实例权限校验（限 mysql）
        try:
            instance = _get_and_check_instance(
                request.user, instance_name, db_type="mysql"
            )
        except Instance.DoesNotExist:
            result["status"] = 1
            result["msg"] = "你所在组未关联该实例！"
            return JsonResponse(result)

        # 检查测试实例的连接信息和 soar 程序路径
        soar_test_dsn = SysConfig().get("soar_test_dsn")
        soar_path = SysConfig().get("soar")
        if not (soar_path and soar_test_dsn):
            result["status"] = 1
            result["msg"] = "请配置soar_path和test_dsn！"
            return JsonResponse(result)

        # 目标实例的连接信息
        online_dsn = (
            f"{instance.user}:{instance.password}@{instance.host}:{instance.port}/{db_name}"
        )

        # 提交给 soar 获取分析报告
        soar = Soar()
        args = {
            "online-dsn": online_dsn,
            "test-dsn": soar_test_dsn,
            "allow-online-as-test": False,
            "report-type": "markdown",
            "query": sql.strip(),
        }
        args_check_result = soar.check_args(args)
        if args_check_result["status"] == 1:
            return JsonResponse(args_check_result)
        cmd_args = soar.generate_args2cmd(args)
        try:
            stdout, stderr = soar.execute_cmd(cmd_args).communicate()
            result["data"] = stdout if stdout else stderr
        except RuntimeError as e:
            result["status"] = 1
            result["msg"] = str(e)
        return JsonResponse(result)


class OptimizeSqlTuningView(APIView):
    """MySQL 调优：系统参数 / SQL 计划 / 对象统计 / 会话状态"""

    permission_classes = [IsAuthenticated, SqlOptimizePermission]

    def post(self, request):
        instance_name = request.data.get("instance_name")
        db_name = request.data.get("db_name")
        sql_content = request.data.get("sql_content")
        # 前端可不传 option，默认采集全部维度
        option = request.data.get("option") or [
            "sys_parm",
            "sql_plan",
            "obj_stat",
            "sql_profile",
        ]
        result = {"status": 0, "msg": "ok", "data": {}}

        # 清理注释，取第一条有效 SQL
        if not sql_content:
            result["status"] = 1
            result["msg"] = "页面提交参数可能为空"
            return JsonResponse(result)
        sqltext = sqlparse.format(sql_content, strip_comments=True)
        sqltext = sqlparse.split(sqltext)[0]
        if re.match(r"^select|^show|^explain", sqltext, re.I) is None:
            result["status"] = 1
            result["msg"] = "只支持查询SQL！"
            return JsonResponse(result)

        # 实例权限校验
        try:
            _get_and_check_instance(request.user, instance_name)
        except Instance.DoesNotExist:
            result["status"] = 1
            result["msg"] = "你所在组未关联该实例！"
            return JsonResponse(result)

        sql_tunning = SqlTuning(
            instance_name=instance_name, db_name=db_name, sqltext=sqltext
        )
        data = {}
        if "sys_parm" in option:
            data["basic_information"] = sql_tunning.basic_information()
            data["sys_parameter"] = sql_tunning.sys_parameter()
            data["optimizer_switch"] = sql_tunning.optimizer_switch()
        if "sql_plan" in option:
            plan, optimizer_rewrite_sql = sql_tunning.sqlplan()
            data["optimizer_rewrite_sql"] = optimizer_rewrite_sql
            data["plan"] = plan
        if "obj_stat" in option:
            data["object_statistics"] = sql_tunning.object_statistics()
        if "sql_profile" in option:
            data["session_status"] = sql_tunning.exec_sql()
        # 关闭连接
        sql_tunning.engine.close()
        data["sqltext"] = sqltext
        result["data"] = data
        return JsonResponse(_encode(result), safe=False)


class ExplainSqlView(APIView):
    """获取 SQL 执行计划"""

    permission_classes = [IsAuthenticated, SqlOptimizePermission]

    def post(self, request):
        sql_content = request.data.get("sql_content")
        instance_name = request.data.get("instance_name")
        db_name = request.data.get("db_name")
        result = {"status": 0, "msg": "ok", "data": []}

        # 服务器端参数验证
        if not sql_content or not instance_name:
            result["status"] = 1
            result["msg"] = "页面提交参数可能为空"
            return JsonResponse(result)

        # 实例权限校验
        try:
            instance = _get_and_check_instance(request.user, instance_name)
        except Instance.DoesNotExist:
            result["status"] = 1
            result["msg"] = "实例不存在"
            return JsonResponse(result)

        # 删除注释语句，进行语法判断，执行第一条有效 sql
        sql_content = sqlparse.format(sql_content.strip(), strip_comments=True)
        try:
            sql_content = sqlparse.split(sql_content)[0]
        except IndexError:
            result["status"] = 1
            result["msg"] = "没有有效的SQL语句"
            return JsonResponse(result)

        # 过滤非 explain 的语句
        if not re.match(r"^explain", sql_content, re.I):
            result["status"] = 1
            result["msg"] = "仅支持explain开头的语句，请检查"
            return JsonResponse(result)

        # 执行获取执行计划语句
        query_engine = get_engine(instance=instance)
        db_name = query_engine.escape_string(db_name)
        result["data"] = query_engine.query(str(db_name), sql_content).to_sep_dict()
        return JsonResponse(_encode(result), safe=False)


# ========== AI 分析 / AI 优化 ==========


class SqlAnalyzeAIView(APIView):
    """AI 评审 SQL（语法/规范/潜在问题），返回 markdown 报告"""

    permission_classes = [IsAuthenticated, SqlAnalyzePermission]

    def post(self, request):
        text = request.data.get("text")
        result = {"status": 0, "msg": "ok", "data": ""}

        if not text:
            result["status"] = 1
            result["msg"] = "请输入 SQL 语句"
            return JsonResponse(result)

        # 校验 openai 是否配置
        if not check_openai_config():
            result["status"] = 1
            result["msg"] = "请先在系统配置的 AI 配置中填写 API Key"
            return JsonResponse(result)

        try:
            report = OpenaiClient().analyze_sql_by_openai(text)
            result["data"] = report
        except ValueError as e:
            result["status"] = 1
            result["msg"] = str(e)
        except Exception as e:
            logger.exception("AI 分析 SQL 异常")
            result["status"] = 1
            result["msg"] = f"AI 分析失败：{e}"
        return JsonResponse(result)


class OptimizeAIView(APIView):
    """AI 优化 SQL（结合表结构），返回 markdown 报告"""

    permission_classes = [IsAuthenticated, SqlOptimizePermission]

    # 拉取表结构的最大表数量，避免 prompt 过长
    MAX_TABLES = 5

    def post(self, request):
        instance_name = request.data.get("instance_name")
        db_name = request.data.get("db_name")
        sql_content = request.data.get("sql_content")
        result = {"status": 0, "msg": "ok", "data": ""}

        if not sql_content or not instance_name:
            result["status"] = 1
            result["msg"] = "页面提交参数可能为空"
            return JsonResponse(result)

        # 校验 openai 是否配置
        if not check_openai_config():
            result["status"] = 1
            result["msg"] = "请先在系统配置的 AI 配置中填写 API Key"
            return JsonResponse(result)

        # 实例权限校验
        try:
            instance = _get_and_check_instance(request.user, instance_name)
        except Instance.DoesNotExist:
            result["status"] = 1
            result["msg"] = "你所在组未关联该实例！"
            return JsonResponse(result)

        # 拉取相关表的建表语句作为上下文
        table_schemas = self._collect_table_schemas(instance, db_name, sql_content)
        try:
            report = OpenaiClient().optimize_sql_by_openai(
                db_type=instance.db_type,
                db_name=db_name,
                sql_text=sql_content,
                table_schemas=table_schemas,
            )
            result["data"] = report
        except ValueError as e:
            result["status"] = 1
            result["msg"] = str(e)
        except Exception as e:
            logger.exception("AI 优化 SQL 异常")
            result["status"] = 1
            result["msg"] = f"AI 优化失败：{e}"
        return JsonResponse(result)

    def _collect_table_schemas(self, instance, db_name, sql_content):
        """从 SQL 中提取表名，拉取每张表的建表语句，拼成上下文文本"""
        try:
            tables = extract_tables(sql_content)
        except Exception:
            tables = []
        if not tables:
            return "(无法解析出表名，仅依据 SQL 文本给出建议)"

        engine = get_engine(instance=instance)
        escaped_db = engine.escape_string(db_name)
        parts = []
        for tb in tables[: self.MAX_TABLES]:
            tb_name = tb.get("name", "").strip("`")
            if not tb_name:
                continue
            try:
                rs = engine.describe_table(escaped_db, tb_name).to_sep_dict()
                # show create table 结果集：第二列是建表语句
                create_ddl = ""
                if rs["rows"]:
                    create_ddl = rs["rows"][0][1] if len(rs["rows"][0]) > 1 else ""
                parts.append(f"-- 表 {tb_name}\n{create_ddl};")
            except Exception:
                # 单张表拉取失败不影响整体
                continue
        engine.close()
        return "\n\n".join(parts) if parts else "(表结构拉取失败，仅依据 SQL 文本给出建议)"
