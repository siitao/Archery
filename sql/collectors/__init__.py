# -*- coding:utf-8 -*-
"""
慢查询采集器模块
"""
from .base import BaseSlowQueryCollector, CursorManager
from .mysql_collector import MySQLSlowQueryCollector
from .pgsql_collector import PgSQLSlowQueryCollector
from .mongo_collector import MongoSlowQueryCollector
from .redis_collector import RedisSlowQueryCollector

__all__ = [
    "BaseSlowQueryCollector",
    "CursorManager",
    "MySQLSlowQueryCollector",
    "PgSQLSlowQueryCollector",
    "MongoSlowQueryCollector",
    "RedisSlowQueryCollector",
]
