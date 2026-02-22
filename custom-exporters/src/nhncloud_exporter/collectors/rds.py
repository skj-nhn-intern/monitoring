"""
RDS for MySQL collector.

NHN Cloud RDS v3.0 API: DB instance status, HA, backups.
수집 간격은 RDS_SCRAPE_INTERVAL(기본 5분). DNS/연결 오류 시 재시도 없이 한 번만 로그.
"""

import logging
from datetime import datetime, timezone

import requests

from nhncloud_exporter import config
from nhncloud_exporter.utils import api_get
from nhncloud_exporter.metrics import (
    exporter_scrape_errors,
    rds_backup_age_seconds,
    rds_instances,
    rds_up,
    rds_backup_count,
    rds_backup_period_days,
    rds_backup_size_bytes,
    rds_backup_status,
    rds_deletion_protection,
    rds_instance_ha,
    rds_instance_port,
    rds_instance_status,
    rds_need_migration,
    rds_need_param_apply,
    rds_replication_type,
)

logger = logging.getLogger("nhncloud-exporter")


class RDSCollector:
    """Collects RDS instance, HA and backup metrics."""

    INSTANCE_STATUS_MAP = {
        "AVAILABLE": 1,
        "FAIL_OVER": 2,
        "FAILOVER": 2,
        "STOPPED": 3,
        "ERROR": 4,
        "CREATING": 5,
        "MODIFYING": 6,
        "BACKING_UP": 7,
        "DELETING": 8,
        "REBOOTING": 9,
    }
    REPL_TYPE_MAP = {
        "STANDALONE": 1,
        "HIGH_AVAILABILITY": 2,
        "READ_REPLICA": 3,
    }
    BACKUP_STATUS_MAP = {
        "COMPLETED": 1,
        "IN_PROGRESS": 2,
        "FAILED": 3,
        "DELETING": 4,
    }

    def collect(self) -> None:
        if not config.NHN_RDS_APPKEY:
            logger.debug("RDS collector skipped: no appkey")
            return

        base = config.NHN_RDS_API_BASE.rstrip("/")
        if "cdn.api" in base or "cdn." in base.split("//")[-1].split("/")[0]:
            logger.error(
                "RDS: NHN_RDS_API_BASE must be RDS API URL (e.g. https://kr1-rds-mysql.api.nhncloudservice.com), "
                "not CDN URL. Current value looks like CDN. Fix .env and restart."
            )
            exporter_scrape_errors.labels(collector="rds").inc()
            return
        if "rds" not in base.lower():
            logger.warning(
                "RDS: NHN_RDS_API_BASE should contain 'rds' (e.g. kr1-rds-mysql.api.nhncloudservice.com). Got: %s",
                base[:80],
            )

        headers = {
            "Content-Type": "application/json",
            "X-TC-APP-KEY": config.NHN_RDS_APPKEY,
            "X-TC-AUTHENTICATION-ID": config.NHN_RDS_SECRETKEY
            if config.NHN_RDS_SECRETKEY
            else config.NHN_USERNAME,
            "X-TC-AUTHENTICATION-SECRET": config.NHN_RDS_SECRETKEY
            if config.NHN_RDS_SECRETKEY
            else config.NHN_PASSWORD,
        }

        rds_up.set(0)
        rds_instances.set(0)
        try:
            # DNS/연결 실패 시 재시도 없이 한 번만 로그 (retry_connection_errors=False)
            inst_data = api_get(
                f"{base}/v3.0/db-instances",
                headers,
                timeout=15,
                retry_connection_errors=False,
            )
            header = inst_data.get("header", {})
            if not header.get("isSuccessful", True) or header.get("resultCode", 0) != 0:
                logger.warning(
                    "RDS API returned error: resultCode=%s, resultMessage=%s",
                    header.get("resultCode"),
                    header.get("resultMessage", ""),
                )
                exporter_scrape_errors.labels(collector="rds").inc()
                return

            db_instances = inst_data.get("dbInstances", [])
            if not isinstance(db_instances, list):
                db_instances = []

            rds_up.set(1)
            rds_instances.set(len(db_instances))

            for inst in db_instances:
                self._collect_instance(inst, base, headers)

            self._collect_backups(base, headers, db_instances)
        except requests.exceptions.HTTPError as e:
            if e.response is not None:
                try:
                    body = e.response.json()
                    h = body.get("header", {})
                    logger.warning(
                        "RDS API HTTP error: %s resultCode=%s %s",
                        e.response.status_code,
                        h.get("resultCode"),
                        h.get("resultMessage", ""),
                    )
                except Exception:
                    logger.warning("RDS API HTTP error: %s", e)
            else:
                logger.warning("RDS API HTTP error: %s", e)
            exporter_scrape_errors.labels(collector="rds").inc()
            rds_up.set(0)
        except requests.exceptions.ConnectionError as e:
            err = str(e).lower()
            if "resolve" in err or "name or service not known" in err:
                logger.warning(
                    "RDS API unreachable (DNS). Check NHN_RDS_API_BASE or set NHN_DISABLE_COLLECTORS=rds"
                )
            else:
                logger.warning("RDS API connection error: %s", e)
            exporter_scrape_errors.labels(collector="rds").inc()
            rds_up.set(0)
        except requests.exceptions.Timeout:
            logger.warning(
                "RDS API timeout. Check NHN_RDS_API_BASE or disable with NHN_DISABLE_COLLECTORS=rds"
            )
            exporter_scrape_errors.labels(collector="rds").inc()
            rds_up.set(0)
        except Exception as e:
            logger.error("RDS collector error: %s", e)
            exporter_scrape_errors.labels(collector="rds").inc()
            rds_up.set(0)

    def _collect_instance(
        self, inst: dict, base: str, headers: dict
    ) -> None:
        db_id = inst.get("dbInstanceId", "")
        db_name = inst.get("dbInstanceName", db_id[:8])
        db_version = inst.get("dbVersion", "")
        db_type = inst.get("dbInstanceType", "")
        db_status = inst.get("dbInstanceStatus", "")
        db_group_id = inst.get("dbInstanceGroupId", "")

        rds_instance_status.labels(
            db_instance_id=db_id,
            db_instance_name=db_name,
            db_version=db_version,
            db_instance_type=db_type,
        ).set(self.INSTANCE_STATUS_MAP.get(db_status.upper(), 0))

        rds_deletion_protection.labels(
            db_instance_id=db_id, db_instance_name=db_name
        ).set(1 if inst.get("useDeletionProtection", False) else 0)

        rds_need_param_apply.labels(
            db_instance_id=db_id, db_instance_name=db_name
        ).set(1 if inst.get("needToApplyParameterGroup", False) else 0)

        rds_need_migration.labels(
            db_instance_id=db_id, db_instance_name=db_name
        ).set(1 if inst.get("needMigration", False) else 0)

        rds_instance_port.labels(
            db_instance_id=db_id, db_instance_name=db_name
        ).set(inst.get("dbPort", 0))

        try:
            detail = api_get(f"{base}/v3.0/db-instances/{db_id}", headers)
            ha_detail = detail.get("highAvailability", {})
            is_ha = bool(ha_detail) or db_type == "HA_MASTER"
            rds_instance_ha.labels(
                db_instance_id=db_id, db_instance_name=db_name
            ).set(1 if is_ha else 0)
        except Exception:
            pass

        if db_group_id:
            try:
                grp_data = api_get(
                    f"{base}/v3.0/db-instance-groups/{db_group_id}", headers
                )
                repl_type = grp_data.get("replicationType", "")
                rds_replication_type.labels(
                    db_instance_group_id=db_group_id,
                    db_instance_name=db_name,
                ).set(self.REPL_TYPE_MAP.get(repl_type.upper(), 0))
            except Exception:
                pass

        try:
            backup_info = api_get(
                f"{base}/v3.0/db-instances/{db_id}/backup-info", headers
            )
            rds_backup_period_days.labels(
                db_instance_id=db_id, db_instance_name=db_name
            ).set(backup_info.get("backupPeriod", 0))
        except Exception:
            pass

    def _collect_backups(
        self, base: str, headers: dict, db_instances: list
    ) -> None:
        try:
            backups_data = api_get(f"{base}/v3.0/backups", headers)
            backups = backups_data.get("backups", [])
            backup_counts = {}
            latest_backup_time = {}

            for bk in backups:
                bk_id = bk.get("backupId", "")
                bk_status = bk.get("backupStatus", "")
                bk_type = bk.get("backupType", "AUTO")
                bk_size = bk.get("backupSize", 0)
                bk_inst_id = bk.get("dbInstanceId", "")

                inst_name = ""
                for inst in db_instances:
                    if inst.get("dbInstanceId") == bk_inst_id:
                        inst_name = inst.get("dbInstanceName", bk_inst_id[:8])
                        break

                rds_backup_status.labels(
                    backup_id=bk_id,
                    db_instance_id=bk_inst_id,
                    db_instance_name=inst_name,
                    backup_type=bk_type,
                ).set(self.BACKUP_STATUS_MAP.get(bk_status.upper(), 0))

                rds_backup_size_bytes.labels(
                    backup_id=bk_id,
                    db_instance_id=bk_inst_id,
                    db_instance_name=inst_name,
                    backup_type=bk_type,
                ).set(bk_size)

                key = (bk_inst_id, inst_name, bk_type)
                backup_counts[key] = backup_counts.get(key, 0) + 1

                if bk_status.upper() == "COMPLETED":
                    completed_at = bk.get("completedYmdt") or bk.get(
                        "updatedYmdt", ""
                    )
                    if completed_at:
                        try:
                            bk_dt = datetime.fromisoformat(
                                completed_at.replace("Z", "+00:00")
                            )
                            age_key = (bk_inst_id, inst_name)
                            if age_key not in latest_backup_time or bk_dt > latest_backup_time[age_key]:
                                latest_backup_time[age_key] = bk_dt
                        except Exception:
                            pass

            for (inst_id, inst_name, bk_type), count in backup_counts.items():
                rds_backup_count.labels(
                    db_instance_id=inst_id,
                    db_instance_name=inst_name,
                    backup_type=bk_type,
                ).set(count)

            now_utc = datetime.now(timezone.utc)
            for (inst_id, inst_name), last_dt in latest_backup_time.items():
                age_secs = (now_utc - last_dt).total_seconds()
                rds_backup_age_seconds.labels(
                    db_instance_id=inst_id, db_instance_name=inst_name
                ).set(max(0, age_secs))

        except Exception as e:
            logger.warning("RDS backup collection error: %s", e)
