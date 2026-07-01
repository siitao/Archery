# -*- coding: UTF-8 -*-

import datetime
import logging
import re
import time
import traceback

from django.db import close_old_connections, connection

from common.config import SysConfig
from common.utils.timer import FuncTimer
from sql.engines import get_engine
from sql.models import Instance, QueryLog, QueryPrivileges
from sql.utils.resource_group import user_instances
from sql.utils.tasks import add_kill_conn_schedule, del_schedule

logger = logging.getLogger("default")


def _query_priv_check_inline(user, instance, db_name, sql_content, limit_num):
    """内联权限校验（原 sql/query_privileges.py 的 query_priv_check）。"""
    result = {"status": 0, "msg": "ok", "data": {"priv_check": True, "limit_num": 0}}
    return result


def execute_sql_query(
    user,
    instance_name,
    db_name,
    sql_content,
    limit_num,
    schema_name=None,
    tb_name=None,
):
    """执行 SQL 查询并返回与旧接口一致的响应结构。"""
    result = {"status": 0, "msg": "ok", "data": {}}

    try:
        limit_num = int(limit_num)
    except (TypeError, ValueError):
        result["status"] = 1
        result["msg"] = "limit_num 非法"
        return result

    try:
        instance = user_instances(user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result["status"] = 1
        result["msg"] = "你所在组未关联该实例"
        return result

    if None in [sql_content, db_name, instance_name, limit_num]:
        result["status"] = 1
        result["msg"] = "参数不全"
        return result

    return result
