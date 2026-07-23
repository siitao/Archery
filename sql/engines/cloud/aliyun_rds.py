# -*- coding: UTF-8 -*-
import simplejson as json
import datetime

from common.utils.aliyun_sdk import Aliyun
from sql.models import AliyunRdsConfig
from sql.engines.mysql import MysqlEngine


class AliyunRDS(MysqlEngine):
    def __init__(self, instance=None):
        super().__init__(instance=instance)
        self.instance_name = instance.instance_name

    # 会话管理（进程列表 / 生成 kill 语句 / kill / 表空间）均直接复用父类
    # MysqlEngine 的原生实现（SHOW PROCESSLIST、information_schema、KILL）。
    # 阿里云 RequestServiceOfCloudDBA 接口已被官方下线，调用会返回
    # HTTP 404 InvalidAction.NotFound，故不再覆写这些方法。
    # 慢日志相关方法仍使用 RDS 独立且有效的 DescribeSlowLogs 系列接口。

    # 获取SQL慢日志统计
    def slowquery_review(self, start_time, end_time, db_name, limit, offset):
        # 计算页数
        page_number = (int(offset) + int(limit)) / int(limit)
        values = {"PageSize": int(limit), "PageNumber": int(page_number)}
        # DBName非必传
        if db_name:
            values["DBName"] = db_name

        # UTC时间转化成阿里云需求的时间格式
        start_time = "%sZ" % start_time
        end_time = "%sZ" % end_time

        # 通过实例名称获取关联的rds实例id
        instance_info = AliyunRdsConfig.objects.get(
            instance__instance_name=self.instance_name
        )
        # 调用aliyun接口获取SQL慢日志统计
        slowsql = Aliyun(rds=instance_info).DescribeSlowLogs(
            start_time, end_time, **values
        )

        # 解决table数据丢失精度、格式化时间
        sql_slow_log = json.loads(slowsql)["Items"]["SQLSlowLog"]
        for SlowLog in sql_slow_log:
            SlowLog["SQLId"] = str(SlowLog["SQLHASH"])
            SlowLog["CreateTime"] = Aliyun.utc2local(
                SlowLog["CreateTime"], utc_format="%Y-%m-%dZ"
            )

        result = {
            "total": json.loads(slowsql)["TotalRecordCount"],
            "rows": sql_slow_log,
            "PageSize": json.loads(slowsql)["PageRecordCount"],
            "PageNumber": json.loads(slowsql)["PageNumber"],
        }
        # 返回查询结果
        return result

    # 获取SQL慢日志明细
    def slowquery_review_history(
        self, start_time, end_time, db_name, sql_id, limit, offset
    ):
        # 计算页数
        page_number = (int(offset) + int(limit)) / int(limit)
        values = {"PageSize": int(limit), "PageNumber": int(page_number)}
        # SQLId、DBName非必传
        if sql_id:
            values["SQLHASH"] = sql_id
        if db_name:
            values["DBName"] = db_name

        # UTC时间转化成阿里云需求的时间格式
        start_time = datetime.datetime.strptime(
            start_time, "%Y-%m-%d"
        ).date() - datetime.timedelta(days=1)
        start_time = "%sT16:00Z" % start_time
        end_time = "%sT15:59Z" % end_time

        # 通过实例名称获取关联的rds实例id
        instance_info = AliyunRdsConfig.objects.get(
            instance__instance_name=self.instance_name
        )
        # 调用aliyun接口获取SQL慢日志统计
        slowsql = Aliyun(rds=instance_info).DescribeSlowLogRecords(
            start_time, end_time, **values
        )

        # 格式化时间\过滤HostAddress
        sql_slow_record = json.loads(slowsql)["Items"]["SQLSlowRecord"]
        for SlowRecord in sql_slow_record:
            SlowRecord["ExecutionStartTime"] = Aliyun.utc2local(
                SlowRecord["ExecutionStartTime"], utc_format="%Y-%m-%dT%H:%M:%SZ"
            )
            # HostAddress 保持原样，不做处理

        result = {
            "total": json.loads(slowsql)["TotalRecordCount"],
            "rows": sql_slow_record,
            "PageSize": json.loads(slowsql)["PageRecordCount"],
            "PageNumber": json.loads(slowsql)["PageNumber"],
        }

        # 返回查询结果
        return result
