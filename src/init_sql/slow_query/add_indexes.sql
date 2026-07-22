-- 慢查询表索引优化
-- 执行时间：2024-XX-XX
-- 说明：为慢查询统计表和明细表添加常用查询索引

-- ========== MySQL 慢查询统计表索引 ==========
-- 按实例+时间范围查询
CREATE INDEX  idx_mysql_sum_inst_lastseen 
    ON mysql_slow_query_summary (instance_id, last_seen);

-- 按实例+数据库名+时间范围查询
CREATE INDEX  idx_mysql_sum_inst_db_lastseen 
    ON mysql_slow_query_summary (instance_id, db_name, last_seen);

-- 按实例+执行时间排序
CREATE INDEX  idx_mysql_sum_inst_exectime 
    ON mysql_slow_query_summary (instance_id, total_execution_times);


-- ========== MySQL 慢查询明细表索引 ==========
-- 重命名现有索引（如果需要）
-- 按实例+SQL哈希+时间范围查询（趋势分析）
CREATE INDEX  idx_mysql_dtl_inst_hash_time 
    ON mysql_slow_query_detail (instance_id, sql_hash, execution_start_time);


-- ========== PgSQL 慢查询统计表索引 ==========
CREATE INDEX  idx_pgsql_sum_inst_lastseen 
    ON pgsql_slow_query_summary (instance_id, last_seen);

CREATE INDEX  idx_pgsql_sum_inst_db_lastseen 
    ON pgsql_slow_query_summary (instance_id, db_name, last_seen);

CREATE INDEX  idx_pgsql_sum_inst_exectime 
    ON pgsql_slow_query_summary (instance_id, total_execution_times);


-- ========== PgSQL 慢查询明细表索引 ==========
CREATE INDEX  idx_pgsql_dtl_inst_hash_time 
    ON pgsql_slow_query_detail (instance_id, sql_hash, execution_start_time);


-- ========== MongoDB 慢查询统计表索引 ==========
CREATE INDEX  idx_mongo_sum_inst_lastseen 
    ON mongo_slow_query_summary (instance_id, last_seen);

CREATE INDEX  idx_mongo_sum_inst_db_lastseen 
    ON mongo_slow_query_summary (instance_id, db_name, last_seen);

CREATE INDEX  idx_mongo_sum_inst_exectime 
    ON mongo_slow_query_summary (instance_id, total_execution_times);


-- ========== MongoDB 慢查询明细表索引 ==========
CREATE INDEX  idx_mongo_dtl_inst_hash_time 
    ON mongo_slow_query_detail (instance_id, sql_hash, execution_start_time);


-- ========== Redis 慢查询统计表索引 ==========
CREATE INDEX  idx_redis_sum_inst_lastseen 
    ON redis_slow_query_summary (instance_id, last_seen);

CREATE INDEX  idx_redis_sum_inst_exectime 
    ON redis_slow_query_summary (instance_id, total_execution_times);


-- ========== Redis 慢查询明细表索引 ==========
CREATE INDEX  idx_redis_dtl_inst_hash_time 
    ON redis_slow_query_detail (instance_id, sql_hash, execution_start_time);

