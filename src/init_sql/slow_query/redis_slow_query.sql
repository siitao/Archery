-- Redis 慢查询统计表
CREATE TABLE IF NOT EXISTS `redis_slow_query_summary` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `instance_id` INT NOT NULL COMMENT '实例ID',
    `sql_hash` VARCHAR(64) NOT NULL COMMENT '命令指纹哈希',
    `fingerprint` TEXT NOT NULL COMMENT '命令指纹',
    `sample_sql` TEXT COMMENT '示例命令',
    `total_execution_counts` INT DEFAULT 0 COMMENT '总执行次数',
    `total_execution_times` FLOAT DEFAULT 0 COMMENT '总执行时间(微秒)',
    `query_time_avg` FLOAT DEFAULT 0 COMMENT '平均执行时间(微秒)',
    `query_time_p95` FLOAT DEFAULT 0 COMMENT '95%执行时间(微秒)',
    `first_seen` DATETIME COMMENT '首次出现时间',
    `last_seen` DATETIME COMMENT '最后出现时间',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `idx_instance_hash` (`instance_id`, `sql_hash`),
    INDEX `idx_last_seen` (`last_seen`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Redis慢查询统计表';

-- Redis 慢查询明细表
CREATE TABLE IF NOT EXISTS `redis_slow_query_detail` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `instance_id` INT NOT NULL COMMENT '实例ID',
    `sql_hash` VARCHAR(64) COMMENT '命令指纹哈希',
    `execution_start_time` DATETIME NOT NULL COMMENT '执行开始时间',
    `host_address` VARCHAR(100) COMMENT '客户端地址',
    `command_text` TEXT NOT NULL COMMENT '命令文本',
    `duration` FLOAT NOT NULL COMMENT '执行耗时(微秒)',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_instance_time` (`instance_id`, `execution_start_time`),
    INDEX `idx_sql_hash` (`sql_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Redis慢查询明细表';
