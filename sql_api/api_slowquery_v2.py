"""
慢查询 API v2 - 支持 MySQL/PgSQL/MongoDB/Redis 统一采集架构

路由：
  POST /api/v1/slowquery/summary/          — 慢查统计
  POST /api/v1/slowquery/detail/           — 慢查明细
  GET  /api/v1/slowquery/trend/            — 慢查趋势
  POST /api/v1/slowquery/collect/          — 手动触发采集

优化说明：
- 提取公共查询构建器，消除重复代码
- 统一时间单位为毫秒（前端无需转换）
- 统一错误处理格式
"""
import datetime as _dt
import logging

from common.utils.extend_json_encoder import encode_json as _encode
from django.db.models import Avg, Count, Max, QuerySet
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from sql.models import (
    Instance,
    MySQLSlowQuerySummary,
    MySQLSlowQueryDetail,
    PgSQLSlowQuerySummary,
    PgSQLSlowQueryDetail,
    MongoSlowQuerySummary,
    MongoSlowQueryDetail,
    RedisSlowQuerySummary,
    RedisSlowQueryDetail,
)
from sql.utils.resource_group import user_instances

logger = logging.getLogger("default")


# ---------- 时间单位常量 ----------
# 统一存储为毫秒，前端无需转换

TIME_UNIT_MS = {
    "mysql": 1000,      # MySQL 存储秒 -> 毫秒
    "pgsql": 1000,      # PgSQL 存储秒 -> 毫秒
    "mongo": 1,         # MongoDB 已经是毫秒
    "redis": 0.001,     # Redis 存储微秒 -> 毫秒
}


# ---------- 统一响应格式 ----------

def success_response(data=None, msg="success"):
    """成功响应"""
    return JsonResponse(_encode({
        "status": 0,
        "msg": msg,
        "data": data
    }))


def error_response(msg="操作失败", status=1):
    """错误响应"""
    return JsonResponse({
        "status": status,
        "msg": msg,
        "data": None
    })


def list_response(rows, total):
    """列表响应"""
    return JsonResponse(_encode({
        "status": 0,
        "msg": "success",
        "total": total,
        "rows": rows
    }))


# ---------- permissions ----------


class SlowQueryV2Permission:
    """慢查询权限检查"""

    def has_permission(self, request, view):
        u = request.user
        return u and u.is_authenticated and (u.is_superuser or u.has_perm("sql.menu_slowquery"))


# ---------- helpers ----------


def _get_and_check_instance(user, instance_name):
    """获取实例并做权限校验"""
    if not instance_name:
        raise Instance.DoesNotExist
    instance = Instance.objects.get(instance_name=instance_name)
    user_instances(user, db_type=[instance.db_type]).get(instance_name=instance_name)
    return instance


def _parse_date(date_str):
    """解析日期字符串"""
    if not date_str:
        return None
    try:
        return _dt.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        try:
            return _dt.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


def _build_queryset(qs, start_dt=None, end_dt=None, db_name=None, search=None,
                    search_field="fingerprint", time_field="last_seen"):
    """
    构建通用查询条件

    Args:
        qs: QuerySet
        start_dt: 开始时间
        end_dt: 结束时间
        db_name: 数据库名
        search: 搜索关键词
        search_field: 搜索字段名
        time_field: 时间字段名
    """
    if start_dt:
        qs = qs.filter(**{f"{time_field}__gte": start_dt})
    if end_dt:
        qs = qs.filter(**{f"{time_field}__lte": end_dt})
    if db_name:
        qs = qs.filter(db_name=db_name)
    if search:
        qs = qs.filter(**{f"{search_field}__icontains": search})
    return qs


def _round_or_zero(value, decimals=2):
    """安全四舍五入，None 返回 0"""
    return round(value or 0, decimals)


def _int_or_zero(value):
    """安全转整数，None 返回 0"""
    return int(value or 0)


# ---------- 查询配置 ----------

# Summary 查询配置
SUMMARY_CONFIG = {
    "mysql": {
        "model": MySQLSlowQuerySummary,
        "fields": [
            "sql_hash", "fingerprint", "sample_sql", "db_name",
            "total_execution_counts", "total_execution_times",
            "query_time_avg", "query_time_p95",
            "parse_total_row_counts", "return_total_row_counts",
            "parse_row_avg", "return_row_avg",
            "first_seen", "last_seen",
        ],
        "field_map": {
            "sql_hash": "SQLId",
            "fingerprint": "SQLText",
            "last_seen": "CreateTime",
            "db_name": "DBName",
            "total_execution_counts": "MySQLTotalExecutionCounts",
            "total_execution_times": "MySQLTotalExecutionTimes",
            "query_time_avg": "QueryTimeAvg",
            "query_time_p95": "QueryTimePct95",
            "parse_total_row_counts": "ParseTotalRowCounts",
            "return_total_row_counts": "ReturnTotalRowCounts",
            "parse_row_avg": "ParseRowAvg",
            "return_row_avg": "ReturnRowAvg",
        },
        "round_fields": ["total_execution_times", "query_time_avg", "query_time_p95"],
        "int_fields": ["parse_row_avg", "return_row_avg"],
    },
    "pgsql": {
        "model": PgSQLSlowQuerySummary,
        "fields": [
            "sql_hash", "fingerprint", "sample_sql", "db_name", "user_name",
            "total_execution_counts", "total_execution_times",
            "query_time_avg", "query_time_p95",
            "rows_sum", "rows_avg",
            "shared_blks_hit", "shared_blks_read",
            "first_seen", "last_seen",
        ],
        "field_map": {
            "sql_hash": "SQLId",
            "fingerprint": "SQLText",
            "last_seen": "CreateTime",
            "db_name": "DBName",
            "total_execution_counts": "TotalExecutionCounts",
            "total_execution_times": "TotalExecutionTimes",
            "query_time_avg": "QueryTimeAvg",
            "query_time_p95": "QueryTimePct95",
            "rows_sum": "ReturnTotalRowCounts",
            "rows_avg": "ReturnRowAvg",
            "shared_blks_hit": "SharedBlksHit",
            "shared_blks_read": "SharedBlksRead",
        },
        "round_fields": ["total_execution_times", "query_time_avg", "query_time_p95", "rows_avg"],
        "int_fields": [],
    },
    "mongo": {
        "model": MongoSlowQuerySummary,
        "fields": [
            "sql_hash", "fingerprint", "sample_sql", "db_name",
            "collection_name", "operation_type",
            "total_execution_counts", "total_execution_times",
            "query_time_avg", "query_time_p95",
            "docs_examined_avg", "docs_returned_avg", "has_sort",
            "first_seen", "last_seen",
        ],
        "field_map": {
            "sql_hash": "SQLId",
            "fingerprint": "SQLText",
            "last_seen": "CreateTime",
            "db_name": "DBName",
            "collection_name": "CollectionName",
            "operation_type": "OperationType",
            "total_execution_counts": "TotalExecutionCounts",
            "total_execution_times": "TotalExecutionTimes",
            "query_time_avg": "QueryTimeAvg",
            "query_time_p95": "QueryTimePct95",
            "docs_examined_avg": "DocsExaminedAvg",
            "docs_returned_avg": "DocsReturnedAvg",
            "has_sort": "HasSort",
        },
        "round_fields": ["total_execution_times", "query_time_avg", "query_time_p95",
                         "docs_examined_avg", "docs_returned_avg"],
        "int_fields": [],
        "bool_fields": {"has_sort": {True: "是", False: "否"}},
    },
    "redis": {
        "model": RedisSlowQuerySummary,
        "fields": [
            "sql_hash", "fingerprint", "sample_sql",
            "total_execution_counts", "total_execution_times",
            "query_time_avg", "query_time_p95",
            "first_seen", "last_seen",
        ],
        "field_map": {
            "sql_hash": "SQLId",
            "fingerprint": "SQLText",
            "last_seen": "CreateTime",
            "total_execution_counts": "TotalExecutionCounts",
            "total_execution_times": "TotalExecutionTimes",
            "query_time_avg": "QueryTimeAvg",
            "query_time_p95": "DurationPct95",
        },
        "round_fields": ["total_execution_times", "query_time_avg", "query_time_p95"],
        "int_fields": [],
    },
}

# Detail 查询配置
DETAIL_CONFIG = {
    "mysql": {
        "model": MySQLSlowQueryDetail,
        "fields": [
            "execution_start_time", "host_address", "db_name", "sql_text",
            "query_time", "lock_time", "rows_sent", "rows_examined",
        ],
        "field_map": {
            "execution_start_time": "ExecutionStartTime",
            "host_address": "HostAddress",
            "db_name": "DBName",
            "sql_text": "SQLText",
            "query_time": "QueryTimes",
            "lock_time": "LockTimes",
            "rows_sent": "ReturnRowCounts",
            "rows_examined": "ParseRowCounts",
        },
        "round_fields": ["query_time", "lock_time"],
        "int_fields": [],
        "time_field": "execution_start_time",
    },
    "pgsql": {
        "model": PgSQLSlowQueryDetail,
        "fields": [
            "execution_start_time", "host_address", "user_name", "db_name", "sql_text",
            "query_time", "rows_sent", "shared_blks_hit", "shared_blks_read",
        ],
        "field_map": {
            "execution_start_time": "ExecutionStartTime",
            "host_address": "HostAddress",
            "db_name": "DBName",
            "sql_text": "SQLText",
            "query_time": "QueryTimes",
            "rows_sent": "ReturnRowCounts",
            "shared_blks_hit": "SharedBlksHit",
            "shared_blks_read": "SharedBlksRead",
        },
        "round_fields": ["query_time"],
        "int_fields": [],
        "time_field": "execution_start_time",
    },
    "mongo": {
        "model": MongoSlowQueryDetail,
        "fields": [
            "execution_start_time", "operation_type", "host_address",
            "db_name", "collection_name", "command_text",
            "duration", "docs_examined", "docs_returned", "nreturned", "has_sort",
        ],
        "field_map": {
            "execution_start_time": "执行时间",
            "operation_type": "操作类型",
            "host_address": "客户端地址",
            "db_name": "数据库",
            "collection_name": "集合",
            "command_text": "命令",
            "duration": "执行耗时(ms)",
            "docs_examined": "扫描文档数",
            "docs_returned": "返回文档数",
            "nreturned": "返回结果数",
            "has_sort": "包含排序",
        },
        "round_fields": ["duration"],
        "int_fields": [],
        "bool_fields": {"has_sort": {True: "是", False: "否"}},
        "time_field": "execution_start_time",
    },
    "redis": {
        "model": RedisSlowQueryDetail,
        "fields": [
            "execution_start_time", "host_address", "command_text", "duration",
        ],
        "field_map": {
            "execution_start_time": "ExecutionStartTime",
            "host_address": "HostName",
            "command_text": "SQLText",
            "duration": "Duration",
        },
        "round_fields": ["duration"],
        "int_fields": [],
        "time_field": "execution_start_time",
    },
}


def _format_rows(rows, config, db_type):
    """
    格式化查询结果行

    Args:
        rows: 原始数据行
        config: 配置信息
        db_type: 数据库类型
    """
    field_map = config["field_map"]
    round_fields = config.get("round_fields", [])
    int_fields = config.get("int_fields", [])
    bool_fields = config.get("bool_fields", {})
    time_unit = TIME_UNIT_MS.get(db_type, 1)

    # 需要进行时间单位转换的字段
    TIME_FIELDS = [
        "total_execution_times", "query_time_avg", "query_time_p95",
        "query_time", "lock_time", "duration",
    ]

    formatted = []
    for row in rows:
        new_row = {}
        for old_key, new_key in field_map.items():
            value = row.get(old_key)

            # 时间单位转换
            if old_key in round_fields and old_key in TIME_FIELDS:
                value = _round_or_zero(value * time_unit if time_unit != 1 else value, 2)
            elif old_key in round_fields:
                value = _round_or_zero(value, 2)

            # 整数转换
            if old_key in int_fields:
                value = _int_or_zero(value)

            # 布尔值转换
            if old_key in bool_fields:
                value = bool_fields[old_key].get(value, str(value))

            new_row[new_key] = value

        formatted.append(new_row)

    return formatted


# ---------- Summary (统计) ----------


class SlowQuerySummaryView(APIView):
    """慢查统计 - 支持 MySQL/PgSQL/MongoDB/Redis"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        instance_name = request.data.get("instance_name")
        start_time = request.data.get("StartTime") or "2010-01-01"
        end_time = request.data.get("EndTime") or _dt.datetime.now().strftime("%Y-%m-%d")
        db_name = request.data.get("db_name")
        search = request.data.get("search", "")
        limit = int(request.data.get("limit") or 50)
        offset = int(request.data.get("offset") or 0)

        try:
            instance = _get_and_check_instance(request.user, instance_name)
        except Instance.DoesNotExist:
            return error_response("你所在组未关联该实例")

        # 解析时间
        start_dt = _parse_date(start_time)
        end_dt = _parse_date(end_time) + _dt.timedelta(days=1) if _parse_date(end_time) else None

        # 检查是否是阿里云 RDS 实例
        from sql.models import AliyunRdsConfig
        is_aliyun_rds = AliyunRdsConfig.objects.filter(instance=instance, is_enable=True).exists()

        try:
            # 根据数据库类型分发
            db_type = instance.db_type
            if is_aliyun_rds:
                result = self._query_aliyun(instance, db_type, start_time, end_time, db_name, limit, offset)
            elif db_type in SUMMARY_CONFIG:
                result = self._query_local(instance, db_type, start_dt, end_dt, db_name, search, limit, offset)
            else:
                return error_response(f"不支持的数据库类型: {db_type}")

            return list_response(result["rows"], result["total"])

        except Exception as e:
            logger.error(f"获取慢查询统计失败: {e}", exc_info=True)
            return error_response(f"获取慢查询统计失败: {e}")

    def _query_aliyun(self, instance, db_type, start_time, end_time, db_name, limit, offset):
        """查询阿里云 RDS 慢查询统计"""
        if db_type == "mysql":
            from sql.engines import get_engine
            engine = get_engine(instance=instance)
            result = engine.slowquery_review(start_time, end_time, db_name, limit, offset)
            # 阿里云MySQL统计返回的时间字段单位是秒，需要乘以1000转为毫秒
            if "rows" in result:
                for row in result["rows"]:
                    # 阿里云返回的字段名
                    for time_field in ["QueryTimeAvg", "QueryTimePct95", "TotalExecutionTimes",
                                       "MySQLTotalExecutionTimes", "QueryTimes", "LockTimes"]:
                        if time_field in row and row[time_field] is not None:
                            row[time_field] = round(float(row[time_field]) * 1000, 2)
            return result
        elif db_type == "mongo":
            from sql.engines.cloud.aliyun_mongo import AliyunMongoEngine
            engine = AliyunMongoEngine(instance=instance)
            return engine.slowquery_review(start_time, end_time, db_name, limit, offset)
        elif db_type == "redis":
            from sql.engines.cloud.aliyun_redis import AliyunRedisEngine
            engine = AliyunRedisEngine(instance=instance)
            result = engine.slowquery_review(start_time, end_time, db_name, limit, offset)
            # 阿里云Redis统计返回的时间字段单位是微秒，需要除以1000转为毫秒
            if "rows" in result:
                for row in result["rows"]:
                    for time_field in ["TotalExecutionTimes", "ElapsedTimeAvg", "ElapsedTimePct95",
                                       "QueryTimeAvg", "QueryTimePct95", "DurationPct95"]:
                        if time_field in row and row[time_field] is not None:
                            row[time_field] = round(float(row[time_field]) / 1000, 2)
            return result
        else:
            raise ValueError(f"阿里云不支持的数据库类型: {db_type}")

    def _query_local(self, instance, db_type, start_dt, end_dt, db_name, search, limit, offset):
        """查询本地数据库慢查询"""
        config = SUMMARY_CONFIG[db_type]
        model = config["model"]

        # 构建查询
        qs = model.objects.filter(instance_id=instance.id)
        qs = _build_queryset(qs, start_dt, end_dt, db_name, search)

        # 统计总数
        total = qs.count()

        # 查询数据
        rows = list(
            qs.order_by("-total_execution_times")
            [offset:offset + limit]
            .values(*config["fields"])
        )

        # 格式化数据
        formatted_rows = _format_rows(rows, config, db_type)

        return {"total": total, "rows": formatted_rows}


# ---------- Detail (明细) ----------


class SlowQueryDetailView(APIView):
    """慢查明细 - 支持 MySQL/PgSQL/MongoDB/Redis"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        instance_name = request.data.get("instance_name")
        start_time = request.data.get("StartTime") or "2010-01-01"
        end_time = request.data.get("EndTime") or _dt.datetime.now().strftime("%Y-%m-%d")
        db_name = request.data.get("db_name")
        sql_id = request.data.get("SQLId")
        search = request.data.get("search", "")
        limit = int(request.data.get("limit") or 50)
        offset = int(request.data.get("offset") or 0)

        try:
            instance = _get_and_check_instance(request.user, instance_name)
        except Instance.DoesNotExist:
            return error_response("你所在组未关联该实例")

        # 解析时间
        start_dt = _parse_date(start_time)
        end_dt = _parse_date(end_time) + _dt.timedelta(days=1) if _parse_date(end_time) else None

        # 检查是否是阿里云 RDS 实例
        from sql.models import AliyunRdsConfig
        is_aliyun_rds = AliyunRdsConfig.objects.filter(instance=instance, is_enable=True).exists()

        try:
            # 根据数据库类型分发
            db_type = instance.db_type
            if is_aliyun_rds:
                result = self._query_aliyun(instance, db_type, start_time, end_time, db_name, sql_id, limit, offset)
            elif db_type in DETAIL_CONFIG:
                result = self._query_local(instance, db_type, start_dt, end_dt, db_name, sql_id, search, limit, offset)
            else:
                return error_response(f"不支持的数据库类型: {db_type}")

            return list_response(result["rows"], result["total"])

        except Exception as e:
            logger.error(f"获取慢查询明细失败: {e}", exc_info=True)
            return error_response(f"获取慢查询明细失败: {e}")

    def _query_aliyun(self, instance, db_type, start_time, end_time, db_name, sql_id, limit, offset):
        """查询阿里云 RDS 慢查询明细"""
        if db_type == "mysql":
            from sql.engines import get_engine
            engine = get_engine(instance=instance)
            result = engine.slowquery_review_history(start_time, end_time, db_name, sql_id, limit, offset)
            # 格式化阿里云 MySQL 返回的字段
            # 注意：阿里云返回的时间单位是秒，需要乘以1000转为毫秒
            if "rows" in result:
                result["rows"] = [
                    {
                        "ExecutionStartTime": row.get("ExecutionStartTime"),
                        "HostAddress": row.get("HostAddress"),
                        "DBName": row.get("DBName"),
                        "SQLText": row.get("SQLText"),
                        "QueryTimes": round(float(row.get("QueryTimes", 0)) * 1000, 2),  # 秒 -> 毫秒
                        "LockTimes": round(float(row.get("LockTimes", 0)) * 1000, 2),  # 秒 -> 毫秒
                        "ParseRowCounts": row.get("ParseRowCounts"),
                        "ReturnRowCounts": row.get("ReturnRowCounts"),
                    }
                    for row in result["rows"]
                ]
            return result
        elif db_type == "mongo":
            from sql.engines.cloud.aliyun_mongo import AliyunMongoEngine
            engine = AliyunMongoEngine(instance=instance)
            result = engine.slowquery_review_history(start_time, end_time, db_name, sql_id, limit, offset)
            # 格式化阿里云 MongoDB 返回的字段
            if "rows" in result:
                result["rows"] = [
                    {
                        "执行时间": row.get("ExecutionStartTime", ""),
                        "客户端地址": row.get("HostAddress", ""),
                        "数据库": row.get("DBName", ""),
                        "集合": row.get("TableName", ""),
                        "命令": row.get("SQLText", ""),
                        "执行耗时(ms)": round(float(row.get("QueryTimes", 0)), 2),
                        "扫描文档数": row.get("DocsExamined", 0),
                        "返回文档数": row.get("ReturnRowCounts", 0),
                    }
                    for row in result["rows"]
                ]
            return result
        elif db_type == "redis":
            from sql.engines.cloud.aliyun_redis import AliyunRedisEngine
            engine = AliyunRedisEngine(instance=instance)
            result = engine.slowquery_review_history(start_time, end_time, db_name, sql_id, limit, offset)
            # 格式化阿里云 Redis 返回的字段
            if "rows" in result:
                result["rows"] = [
                    {
                        "ExecutionStartTime": row.get("ExecuteTime", ""),
                        "HostName": row.get("IPAddress", ""),
                        "SQLText": row.get("Command", ""),
                        "Duration": round(float(row.get("ElapsedTime", 0)) / 1000, 3),
                    }
                    for row in result["rows"]
                ]
            return result
        else:
            raise ValueError(f"阿里云不支持的数据库类型: {db_type}")

    def _query_local(self, instance, db_type, start_dt, end_dt, db_name, sql_id, search, limit, offset):
        """查询本地数据库慢查询明细"""
        config = DETAIL_CONFIG[db_type]
        model = config["model"]
        time_field = config.get("time_field", "execution_start_time")

        # 构建查询
        qs = model.objects.filter(instance_id=instance.id)
        qs = _build_queryset(qs, start_dt, end_dt, db_name, search,
                            search_field="sql_text" if db_type != "mongo" else "command_text",
                            time_field=time_field)

        # SQL ID 过滤
        if sql_id:
            qs = qs.filter(sql_hash=sql_id)

        # 统计总数
        total = qs.count()

        # 查询数据
        rows = list(
            qs.order_by(f"-{time_field}")
            [offset:offset + limit]
            .values(*config["fields"])
        )

        # 格式化数据
        formatted_rows = _format_rows(rows, config, db_type)

        return {"total": total, "rows": formatted_rows}


# ---------- Trend (趋势) ----------


class SlowQueryTrendView(APIView):
    """慢查趋势 - 支持所有数据库类型"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        instance_name = request.query_params.get("instance_name")
        sql_hash = request.query_params.get("sql_hash")
        days = int(request.query_params.get("days", 7))

        try:
            instance = _get_and_check_instance(request.user, instance_name)
        except Instance.DoesNotExist:
            return error_response("你所在组未关联该实例")

        if not sql_hash:
            return error_response("缺少 sql_hash 参数")

        # 计算时间范围
        end_dt = _dt.datetime.now()
        start_dt = end_dt - _dt.timedelta(days=days)

        try:
            db_type = instance.db_type
            if db_type == "mysql":
                result = self._query_trend(MySQLSlowQueryDetail, instance, sql_hash, start_dt, end_dt, "query_time")
            elif db_type == "pgsql":
                result = self._query_trend(PgSQLSlowQueryDetail, instance, sql_hash, start_dt, end_dt, "query_time")
            elif db_type == "mongo":
                result = self._query_trend(MongoSlowQueryDetail, instance, sql_hash, start_dt, end_dt, "duration")
            elif db_type == "redis":
                result = self._query_trend(RedisSlowQueryDetail, instance, sql_hash, start_dt, end_dt, "duration")
            else:
                return error_response(f"不支持的数据库类型: {db_type}")

            return success_response(result)

        except Exception as e:
            logger.error(f"获取慢查询趋势失败: {e}", exc_info=True)
            return error_response(f"获取慢查询趋势失败: {e}")

    def _query_trend(self, model, instance, sql_hash, start_dt, end_dt, time_field):
        """查询趋势数据"""
        qs = model.objects.filter(
            instance_id=instance.id,
            sql_hash=sql_hash,
            execution_start_time__gte=start_dt,
            execution_start_time__lte=end_dt,
        )

        # 按日期聚合
        trend = (
            qs.annotate(date=TruncDate("execution_start_time"))
            .values("date")
            .annotate(
                count=Count("id"),
                avg_time=Avg(time_field),
                max_time=Max(time_field),
            )
            .order_by("date")
        )

        # 格式化结果
        rows = [
            {
                "date": item["date"].strftime("%Y-%m-%d"),
                "count": item["count"],
                "avg_time": round(item["avg_time"] or 0, 2),
                "max_time": round(item["max_time"] or 0, 2),
            }
            for item in trend
        ]

        return rows


# ---------- Collect (采集) ----------


class SlowQueryCollectView(APIView):
    """手动触发慢查询采集"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        instance_name = request.data.get("instance_name")
        collect_type = request.data.get("type", "all")

        if not instance_name:
            return error_response("缺少 instance_name 参数")

        try:
            instance = _get_and_check_instance(request.user, instance_name)
        except Instance.DoesNotExist:
            return error_response("你所在组未关联该实例")

        # 异步执行采集任务
        try:
            from sql.collectors.tasks import collect_slowquery_task

            task_id = collect_slowquery_task(instance.id, collect_type)
            return success_response({"task_id": task_id}, "采集任务已提交")

        except Exception as e:
            logger.error(f"提交采集任务失败: {e}", exc_info=True)
            return error_response(f"提交采集任务失败: {e}")
