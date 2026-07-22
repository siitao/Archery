-- PgSQL 慢查询统计表
CREATE TABLE IF NOT EXISTS `pgsql_slow_query_summary` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `instance_id` INT NOT NULL COMMENT '实例ID',
    `sql_hash` VARCHAR(64) NOT NULL COMMENT 'SQL指纹哈希(queryid)',
    `fingerprint` TEXT NOT NULL COMMENT 'SQL指纹',
    `sample_sql` TEXT COMMENT '示例SQL',
    `db_name` VARCHAR(100) COMMENT '数据库名',
    `user_name` VARCHAR(100) COMMENT '用户名',
    `total_execution_counts` INT DEFAULT 0 COMMENT '总执行次数',
    `total_execution_times` FLOAT DEFAULT 0 COMMENT '总执行时间(秒)',
    `query_time_avg` FLOAT DEFAULT 0 COMMENT '平均执行时间(秒)',
    `query_time_p95` FLOAT DEFAULT 0 COMMENT '95%执行时间(秒)',
    `rows_sum` BIGINT DEFAULT 0 COMMENT '总返回行数',
    `rows_avg` FLOAT DEFAULT 0 COMMENT '平均返回行数',
    `shared_blks_hit` BIGINT DEFAULT 0 COMMENT '缓存命中块数',
    `shared_blks_read` BIGINT DEFAULT 0 COMMENT '磁盘读取块数',
    `first_seen` DATETIME COMMENT '首次出现时间',
    `last_seen` DATETIME COMMENT '最后出现时间',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `idx_instance_hash` (`instance_id`, `sql_hash`),
    INDEX `idx_last_seen` (`last_seen`),
    INDEX `idx_db_name` (`db_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='PgSQL慢查询统计表';

-- PgSQL 慢查询明细表
CREATE TABLE IF NOT EXISTS `pgsql_slow_query_detail` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `instance_id` INT NOT NULL COMMENT '实例ID',
    `sql_hash` VARCHAR(64) COMMENT 'SQL指纹哈希',
    `execution_start_time` DATETIME NOT NULL COMMENT '执行开始时间',
    `host_address` VARCHAR(100) COMMENT '客户端地址',
    `user_name` VARCHAR(100) COMMENT '用户名',
    `db_name` VARCHAR(100) COMMENT '数据库名',
    `sql_text` TEXT NOT NULL COMMENT 'SQL文本',
    `query_time` FLOAT NOT NULL COMMENT '执行耗时(秒)',
    `rows_sent` INT DEFAULT 0 COMMENT '返回行数',
    `shared_blks_hit` INT DEFAULT 0 COMMENT '缓存命中块数',
    `shared_blks_read` INT DEFAULT 0 COMMENT '磁盘读取块数',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_instance_time` (`instance_id`, `execution_start_time`),
    INDEX `idx_sql_hash` (`sql_hash`),
    INDEX `idx_db_name` (`db_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='PgSQL慢查询明细表';
