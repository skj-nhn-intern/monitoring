"""Exporter entry point: HTTP server and collector loop."""

import logging
import threading
import time

from prometheus_client import start_http_server

from nhncloud_exporter import config
from nhncloud_exporter.auth import token_mgr, is_lb_oauth2
from nhncloud_exporter.metrics import (
    exporter_scrape_duration,
    exporter_scrape_errors,
    exporter_up,
)
from nhncloud_exporter.collectors import (
    LoadBalancerCollector,
    CDNCollector,
    RDSCollector,
    OBSCollector,
)


def _obs_health_check_loop() -> None:
    """Run OBS health check every OBS_HEALTH_CHECK_INTERVAL (default 30s)."""
    logger = logging.getLogger("nhncloud-exporter")
    collector = OBSCollector()
    interval = config.OBS_HEALTH_CHECK_INTERVAL
    while True:
        try:
            collector.collect()
        except Exception as e:
            logger.error("OBS health check loop error: %s", e)
        time.sleep(interval)


def run_collectors() -> None:
    """Run collectors in a loop. LB/CDN: SCRAPE_INTERVAL, RDS: RDS_SCRAPE_INTERVAL(기본 5분)."""
    all_collectors = [
        ("loadbalancer", LoadBalancerCollector()),
        ("cdn", CDNCollector()),
        ("rds", RDSCollector()),
    ]
    disabled = config.DISABLE_COLLECTORS
    collectors = [(n, c) for n, c in all_collectors if n not in disabled]
    logger = logging.getLogger("nhncloud-exporter")
    if disabled:
        logger.debug("Disabled collectors: %s", sorted(disabled))

    # RDS는 RDS_SCRAPE_INTERVAL마다만 실행 (DB 상태는 자주 안 바뀌고, DNS 오류 시 로그 스팸 완화)
    last_rds_run = 0.0

    if config.OBS_PUBLIC_HEALTH_CHECK_URLS:
        obs_thread = threading.Thread(
            target=_obs_health_check_loop,
            name="obs-health-check",
            daemon=True,
        )
        obs_thread.start()
        logger.debug(
            "OBS health check started (interval=%ds, urls=%d)",
            config.OBS_HEALTH_CHECK_INTERVAL,
            len(config.OBS_PUBLIC_HEALTH_CHECK_URLS),
        )

    if "rds" not in disabled and config.NHN_RDS_APPKEY:
        logger.debug(
            "RDS collector interval: %ds (SCRAPE_INTERVAL=%ds for LB/CDN)",
            config.RDS_SCRAPE_INTERVAL,
            config.SCRAPE_INTERVAL,
        )

    while True:
        now = time.time()
        for name, collector in collectors:
            if name == "rds":
                if now - last_rds_run < config.RDS_SCRAPE_INTERVAL:
                    continue
                last_rds_run = now
            start = time.time()
            try:
                collector.collect()
                duration = time.time() - start
                exporter_scrape_duration.labels(collector=name).observe(duration)
                logger.debug("Collector '%s' completed in %.2fs", name, duration)
            except Exception as e:
                exporter_scrape_errors.labels(collector=name).inc()
                logger.error("Collector '%s' failed: %s", name, e)

        exporter_up.set(1)
        time.sleep(config.SCRAPE_INTERVAL)


def main() -> None:
    """Configure logging, start HTTP server, pre-auth, run collector loop."""
    logger = config.setup_logging()

    logger.info(
        "NHN Cloud Exporter starting port=%d interval=%ds",
        config.EXPORTER_PORT,
        config.SCRAPE_INTERVAL,
    )
    if config.NHN_NETWORK_ENDPOINT:
        logger.debug(
            "LB auth: %s",
            "OAuth2 (User Access Key)" if is_lb_oauth2() else "Keystone (tenant/user/password)",
        )
    if not config.NHN_TENANT_ID or not config.NHN_USERNAME:
        logger.warning(
            "NHN_TENANT_ID or NHN_USERNAME not set - LB/OBS collectors may fail"
        )
    if config.NHN_OBS_TARGETS and not config.NHN_OBS_API_URL:
        logger.debug(
            "NHN_OBS_API_URL not set - OBS URL will be taken from token catalog if available"
        )

    start_http_server(config.EXPORTER_PORT)
    logger.debug("Prometheus metrics server started on :%d", config.EXPORTER_PORT)

    try:
        token_mgr.get_token()
    except Exception:
        logger.warning("Initial token acquisition failed - will retry")

    run_collectors()
