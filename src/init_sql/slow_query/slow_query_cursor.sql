-- 慢查询采集游标表（用于增量采集）
CREATE TABLE IF NOT EXISTS `slow_query_cursor` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `instance_id` INT NOT NULL COMMENT '实例ID',
    `db_type` VARCHAR(20) NOT NULL COMMENT '数据库类型(mysql/pgsql/mongo/redis)',
    `last_cursor` DATETIME COMMENT '上次采集的时间戳',
    `last_cursor_id` BIGINT COMMENT '上次采集的ID（可选）',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `idx_instance_dbtype` (`instance_id`, `db_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='慢查询采集游标表';
