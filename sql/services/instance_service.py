"""
实例 + 引擎解析服务 · 消除 api_instance_admin / api_dictionary 中的重复模式。

API 视图直接 import 使用，替代各自私有的 _get_instance / _get_engine。
"""
from sql.engines import get_engine
from sql.models import Instance
from sql.utils.resource_group import user_instances

import logging

logger = logging.getLogger("default")


def resolve_instance(user, instance_id=None, instance_name=None, db_type=None):
    """
    通过 instance_id 或 instance_name 查找 Instance，并做资源组权限校验。

    参数：
        user: 请求用户
        instance_id: 实例 ID（来自 POST data 或 GET param）
        instance_name: 实例名（优先级低于 instance_id）
        db_type: 限定数据库类型（单值或列表均可）

    返回：
        Instance 对象

    抛出：
        Instance.DoesNotExist — 实例不存在或用户所在组未关联
    """
    if db_type is None:
        db_type_filter = []
    elif isinstance(db_type, str):
        db_type_filter = [db_type]
    else:
        db_type_filter = list(db_type)

    if instance_id:
        return user_instances(user, db_type=db_type_filter).get(id=instance_id)
    if instance_name:
        return user_instances(user, db_type=db_type_filter).get(
            instance_name=instance_name
        )
    raise Instance.DoesNotExist("未提供 instance_id 或 instance_name")


def resolve_instance_and_engine(user, instance_id=None, instance_name=None, db_type=None):
    """
    resolve_instance + get_engine，返回 (instance, engine) 元组。
    """
    instance = resolve_instance(
        user, instance_id=instance_id, instance_name=instance_name, db_type=db_type
    )
    return instance, get_engine(instance=instance)
