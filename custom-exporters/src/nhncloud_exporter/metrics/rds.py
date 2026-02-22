"""RDS for MySQL Prometheus metrics."""

from prometheus_client import Gauge

rds_up = Gauge(
    "nhncloud_rds_up",
    "RDS API scrape success (1=ok, 0=fail or skipped)",
    [],
)
rds_instances = Gauge(
    "nhncloud_rds_instances",
    "Number of DB instances returned by API",
    [],
)
rds_instance_status = Gauge(
    "nhncloud_rds_instance_status",
    "DB instance status (1=AVAILABLE,2=FAIL_OVER,3=STOPPED,4=ERROR,0=OTHER)",
    ["db_instance_id", "db_instance_name", "db_version", "db_instance_type"],
)
rds_instance_ha = Gauge(
    "nhncloud_rds_instance_ha_enabled",
    "High availability enabled (1=yes,0=no)",
    ["db_instance_id", "db_instance_name"],
)
rds_replication_type = Gauge(
    "nhncloud_rds_replication_type",
    "Replication type (1=STANDALONE,2=HIGH_AVAILABILITY,3=READ_REPLICA,0=UNKNOWN)",
    ["db_instance_group_id", "db_instance_name"],
)
rds_instance_port = Gauge(
    "nhncloud_rds_instance_port",
    "DB instance port",
    ["db_instance_id", "db_instance_name"],
)
rds_deletion_protection = Gauge(
    "nhncloud_rds_deletion_protection",
    "Deletion protection enabled",
    ["db_instance_id", "db_instance_name"],
)
rds_need_param_apply = Gauge(
    "nhncloud_rds_need_param_group_apply",
    "Parameter group needs apply",
    ["db_instance_id", "db_instance_name"],
)
rds_need_migration = Gauge(
    "nhncloud_rds_need_migration",
    "DB instance needs migration",
    ["db_instance_id", "db_instance_name"],
)

rds_backup_status = Gauge(
    "nhncloud_rds_backup_status",
    "Backup status (1=COMPLETED,2=IN_PROGRESS,3=FAILED,0=OTHER)",
    ["backup_id", "db_instance_id", "db_instance_name", "backup_type"],
)
rds_backup_size_bytes = Gauge(
    "nhncloud_rds_backup_size_bytes",
    "Backup size in bytes",
    ["backup_id", "db_instance_id", "db_instance_name", "backup_type"],
)
rds_backup_age_seconds = Gauge(
    "nhncloud_rds_backup_latest_age_seconds",
    "Seconds since last successful backup",
    ["db_instance_id", "db_instance_name"],
)
rds_backup_count = Gauge(
    "nhncloud_rds_backup_count",
    "Total backup count",
    ["db_instance_id", "db_instance_name", "backup_type"],
)
rds_backup_period_days = Gauge(
    "nhncloud_rds_backup_retention_period_days",
    "Backup retention period in days",
    ["db_instance_id", "db_instance_name"],
)
