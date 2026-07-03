--
-- Schema Sync 0.9.4 Revert Script
-- Created: Thu, Jul 02, 2026
-- Server Version: 5.7.44
-- Apply To: 192.168.0.164/nginxui
--

USE `nginxui`;
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE `audit_logs`;
DROP TABLE `cert_deployment`;
DROP TABLE `cert_notification_log`;
DROP TABLE `config_templates`;
DROP TABLE `dns_credentials`;
DROP TABLE `schema_migrations`;
DROP TABLE `ssl_certificate_logs`;
DROP TABLE `system_settings`;
CREATE TABLE `aliyun_credentials` ( `id` int(11) NOT NULL AUTO_INCREMENT, `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL, `access_key_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL, `access_key_secret` text COLLATE utf8mb4_unicode_ci NOT NULL, `region` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT 'cn-beijing', `description` text COLLATE utf8mb4_unicode_ci, `is_default` tinyint(1) DEFAULT '0', `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP, `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, PRIMARY KEY (`id`), KEY `idx_name` (`name`), KEY `idx_is_default` (`is_default`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
ALTER TABLE `nginx_config_versions` DROP COLUMN `created_by`, DROP INDEX `idx_config_version`;
ALTER TABLE `nginx_hosts` DROP COLUMN `host_key`, DROP COLUMN `cert_dir`;
ALTER TABLE `ssl_certificates` DROP COLUMN `dns_provider`, DROP COLUMN `dns_credential_key`, DROP COLUMN `dns_credential_secret`, DROP COLUMN `source_type`, ADD COLUMN `aliyun_access_key_id` varchar(255) NULL AFTER `fullchain_path`, ADD COLUMN `aliyun_access_key_secret` text NULL AFTER `aliyun_access_key_id`, DROP INDEX `idx_dns_provider`, DROP INDEX `idx_source_type`, DROP INDEX `idx_cert_renewal`;
ALTER TABLE `users` DROP COLUMN `last_login_at`, DROP COLUMN `login_count`;
SET FOREIGN_KEY_CHECKS = 1;
DROP VIEW `aliyun_credentials`;
