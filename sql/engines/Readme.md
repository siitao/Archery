# Engine 说明

## Cassandra
当前连接时, 使用参数基本为写死参数, 具体可以参照代码.

如果需要覆盖, 可以自行继承

具体方法为:
1. 新增一个文件夹`extras`在根目录, 和`sql`, `sql_api`等文件夹平级 可以docker 打包时加入, 也可以使用卷挂载的方式
2. 新增一个文件, `mycassandra.py`
```python
from sql.engines.cassandra import CassandraEngine

class MyCassandraEngine(CassandraEngine):
    def get_connection(self, db_name=None):
        db_name = db_name or self.db_name
        if self.conn:
            if db_name:
                self.conn.execute(f"use {db_name}")
            return self.conn
        hosts = self.host.split(",")
        # 在这里更改你获取 session 的方式
        auth_provider = PlainTextAuthProvider(
            username=self.user, password=self.password
        )
        cluster = Cluster(hosts, port=self.port, auth_provider=auth_provider,
                          load_balancing_policy=RoundRobinPolicy(), protocol_version=5)
        self.conn = cluster.connect(keyspace=db_name)
        # 下面这一句最好是不要动.
        self.conn.row_factory = tuple_factory
        return self.conn
```
3. 修改settings , 加载你刚写的 engine
```python
AVAILABLE_ENGINES = {
    "mysql": {"path": "sql.engines.mysql:MysqlEngine"},
    # 这里改成你的 engine
    "cassandra": {"path": "extras.mycassandra:MyCassandraEngine"},
    "clickhouse": {"path": "sql.engines.clickhouse:ClickHouseEngine"},
    "goinception": {"path": "sql.engines.goinception:GoInceptionEngine"},
    "mssql": {"path": "sql.engines.mssql:MssqlEngine"},
    "redis": {"path": "sql.engines.redis:RedisEngine"},
    "pqsql": {"path": "sql.engines.pgsql:PgSQLEngine"},
    "oracle": {"path": "sql.engines.oracle:OracleEngine"},
    "mongo": {"path": "sql.engines.mongo:MongoEngine"},
    "phoenix": {"path": "sql.engines.phoenix:PhoenixEngine"},
    "odps": {"path": "sql.engines.odps:ODPSEngine"},
}
```

## PgSQL 引擎功能支持矩阵

PgSQL 引擎（`sql/engines/pgsql.py`）基于 `psycopg2` 驱动，`pglast` 做 SQL 语法树审核。支持的功能如下：

| 功能模块 | 支持情况 | 说明 |
|---------|---------|------|
| 在线查询 | ✅ | SELECT/EXPLAIN，支持 schema 选择、JSONB 转换、只读事务 |
| SQL 工单审核 | ✅ | 基于 pglast AST：语法校验、DROP/TRUNCATE 拦截、无 WHERE 的 UPDATE/DELETE 告警、高危正则、critical_ddl_regex |
| 工单执行 | ✅ | 逐条执行、失败回滚、异常标记 |
| 数据字典 | ✅ | 表/视图/函数/存储过程/触发器的列表与详情（基于 pg_catalog）|
| 诊断 | ✅ | 进程列表(pg_stat_activity)、锁等待(pg_blocking_pids)、长事务、终止会话(pg_terminate_backend)、Top 表空间(表维度 TOP N，按 pg_total_relation_size 排序) |
| 参数管理 | ✅ | 查 pg_settings、ALTER SYSTEM SET（postmaster 类参数需重启会被拒绝）|
| 参数对比 | ✅ | 两个 PG 实例间参数对比 |
| 数据库对象管理 | ❌ | 账号管理（create/drop instance user）暂不支持 |
| 回滚 SQL | ❌ | 暂不生成回滚语句 |
| 定时任务(events) | ❌ | PG 无原生事件调度（pg_cron 扩展可后续支持）|

### 审核依赖
工单审核依赖 `pglast==6.*`（PostgreSQL 官方 libpg_query 的 Python 绑定），安装见 `requirements.txt`。pglast 包含 C 扩展，部分平台（如 Windows 无 MSVC）需预编译环境或使用官方 wheel。

### schema 说明
PG 有独立的 schema 概念（区别于 MySQL）。数据字典、对象管理方法默认查询 `public` schema，可通过 `schema_name` 参数指定其他 schema（在线查询页已支持 schema 选择器）。