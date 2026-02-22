"""
Object Storage (OBS) health check collector.

Performs API health checks at a fixed interval (default 30s) for multiple
targets (containers or container/object paths), e.g. for replicated objects.
"""

import logging
import time
from typing import Optional

import requests

from nhncloud_exporter import config
from nhncloud_exporter.auth import token_mgr
from nhncloud_exporter.metrics import (
    exporter_scrape_duration,
    exporter_scrape_errors,
    obs_health_check_duration_seconds,
    obs_health_check_up,
)

logger = logging.getLogger("nhncloud-exporter")


def _get_obs_base_url() -> Optional[str]:
    """Object Storage base URL: v1/AUTH_tenant_id prefix."""
    account = f"AUTH_{config.NHN_TENANT_ID}" if config.NHN_TENANT_ID else "default"
    base = config.NHN_OBS_API_URL
    if not base:
        catalog = token_mgr.service_catalog
        obj_svc = catalog.get("object-store")
        if obj_svc:
            endpoints = obj_svc.get("endpoints", [])
            if endpoints:
                public_url = endpoints[0].get("publicURL", "").rstrip("/")
                if public_url:
                    base = public_url
    if not base:
        return None
    return f"{base.rstrip('/')}/v1/{account}"


class OBSCollector:
    """Performs HEAD-based health checks for configured OBS targets."""

    def collect(self) -> None:
        if not config.NHN_OBS_TARGETS:
            return

        base_url = _get_obs_base_url()
        if not base_url:
            logger.warning(
                "OBS health check skipped: no NHN_OBS_API_URL and no object-store in token catalog"
            )
            return

        if not config.NHN_TENANT_ID or not config.NHN_USERNAME:
            logger.warning(
                "OBS health check skipped: NHN_TENANT_ID or NHN_USERNAME not set"
            )
            return

        start = time.time()
        try:
            token = token_mgr.get_token()
            headers = {"X-Auth-Token": token}

            for target in config.NHN_OBS_TARGETS:
                # target: "container" or "container/object_key"
                url = f"{base_url}/{target}"
                t0 = time.time()
                try:
                    resp = requests.head(url, headers=headers, timeout=10)
                    success = 200 <= resp.status_code < 400
                    obs_health_check_up.labels(target=target).set(1 if success else 0)
                except Exception as e:
                    logger.debug("OBS health check %s failed: %s", target, e)
                    obs_health_check_up.labels(target=target).set(0)
                    success = False
                duration = time.time() - t0
                obs_health_check_duration_seconds.labels(target=target).set(
                    round(duration, 4)
                )
                if not success:
                    logger.warning(
                        "OBS health check failed for target %s (%.2fs)", target, duration
                    )

            exporter_scrape_duration.labels(collector="obs").observe(
                time.time() - start
            )
        except Exception as e:
            logger.error("OBS collector error: %s", e)
            exporter_scrape_errors.labels(collector="obs").inc()
            for target in config.NHN_OBS_TARGETS:
                obs_health_check_up.labels(target=target).set(0)
