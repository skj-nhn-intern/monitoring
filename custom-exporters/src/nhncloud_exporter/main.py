"""Exporter entry point: HTTP server and collector loop."""

import logging
import threading
import time

from prometheus_client import start_http_server

from nhncloud_exporter import config
from nhncloud_exporter.auth import token_mgr
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
    """Run all collectors in a loop with SCRAPE_INTERVAL."""
    collectors = [
        ("loadbalancer", LoadBalancerCollector()),
        ("cdn", CDNCollector()),
        ("rds", RDSCollector()),
    ]
    logger = logging.getLogger("nhncloud-exporter")

    if config.NHN_OBS_TARGETS:
        obs_thread = threading.Thread(
            target=_obs_health_check_loop,
            name="obs-health-check",
            daemon=True,
        )
        obs_thread.start()
        logger.info(
            "OBS health check started (interval=%ds, targets=%s)",
            config.OBS_HEALTH_CHECK_INTERVAL,
            config.NHN_OBS_TARGETS,
        )

    while True:
        for name, collector in collectors:
            start = time.time()
            try:
                collector.collect()
                duration = time.time() - start
                exporter_scrape_duration.labels(collector=name).observe(duration)
                logger.info("Collector '%s' completed in %.2fs", name, duration)
            except Exception as e:
                exporter_scrape_errors.labels(collector=name).inc()
                logger.error("Collector '%s' failed: %s", name, e)

        exporter_up.set(1)
        time.sleep(config.SCRAPE_INTERVAL)


def main() -> None:
    """Configure logging, start HTTP server, pre-auth, run collector loop."""
    logger = config.setup_logging()

    logger.info("=" * 60)
    logger.info("NHN Cloud Prometheus Exporter starting...")
    logger.info("Port: %d | Interval: %ds", config.EXPORTER_PORT, config.SCRAPE_INTERVAL)
    logger.info("=" * 60)

    if not config.NHN_TENANT_ID or not config.NHN_USERNAME:
        logger.warning(
            "NHN_TENANT_ID or NHN_USERNAME not set - LB/OBS collectors may fail"
        )
    if config.NHN_OBS_TARGETS and not config.NHN_OBS_API_URL:
        logger.info(
            "NHN_OBS_API_URL not set - OBS URL will be taken from token catalog if available"
        )

    start_http_server(config.EXPORTER_PORT)
    logger.info("Prometheus metrics server started on :%d", config.EXPORTER_PORT)

    try:
        token_mgr.get_token()
    except Exception:
        logger.warning("Initial token acquisition failed - will retry")

    run_collectors()
