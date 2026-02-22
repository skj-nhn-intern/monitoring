"""
Object Storage (OBS) health check collector.

Performs API health checks at a fixed interval (default 30s) for multiple
targets (containers or container/object paths). Public OBS도 동일 Swift API를
사용하므로 토큰으로 HEAD 요청 가능.

URL 구조: {base}/v1/AUTH_tenant_id/{target}
- target은 반드시 container 이름 또는 container/object_key (예: photo, photo/image.png)
"""

import logging
import re
import time
from typing import List, Tuple
from urllib.parse import urlparse

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


def _region_from_url(url: str) -> str:
    """Derive a short region label from OBS API URL (e.g. kr1-objectstorage... -> kr1)."""
    try:
        host = urlparse(url).netloc
        if not host:
            return "default"
        # kr1-, kr2-, us1- 등 리전 접두사 추출
        m = re.match(r"^([a-z]{2}\d+)[-_]", host, re.IGNORECASE)
        if m:
            return m.group(1).lower()
        return host.split(".")[0].replace("-", "_") if host else "default"
    except Exception:
        return "default"


def _get_obs_base_urls() -> List[Tuple[str, str]]:
    """
    Build list of (region, full_base_url) for OBS.
    full_base_url = {api_base}/v1/AUTH_tenant_id (container는 포함하지 않음; target으로 추가).
    리전 무관: NHN_OBS_API_URLS 여러 개 설정 시 각 URL마다 헬스 체크.
    """
    account = f"AUTH_{config.NHN_TENANT_ID}" if config.NHN_TENANT_ID else "default"
    bases: List[Tuple[str, str]] = []

    if config.NHN_OBS_API_URLS:
        for base in config.NHN_OBS_API_URLS:
            region = _region_from_url(base)
            full = f"{base.rstrip('/')}/v1/{account}"
            bases.append((region, full))
        return bases

    if config.NHN_OBS_API_URL:
        region = _region_from_url(config.NHN_OBS_API_URL)
        full = f"{config.NHN_OBS_API_URL.rstrip('/')}/v1/{account}"
        bases.append((region, full))
        return bases

    catalog = token_mgr.service_catalog
    obj_svc = catalog.get("object-store")
    if obj_svc:
        for ep in obj_svc.get("endpoints", []):
            public_url = (ep.get("publicURL") or "").strip().rstrip("/")
            if public_url:
                region = ep.get("region") or _region_from_url(public_url)
                full = f"{public_url}/v1/{account}"
                bases.append((str(region), full))
    return bases


class OBSCollector:
    """Performs HEAD-based health checks for configured OBS targets (container or container/object_key)."""

    def collect(self) -> None:
        if not config.NHN_OBS_TARGETS:
            return

        base_list = _get_obs_base_urls()
        if not base_list:
            logger.warning(
                "OBS health check skipped: set NHN_OBS_API_URL or NHN_OBS_API_URLS, or ensure object-store in token catalog"
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

            for region, base_url in base_list:
                for target in config.NHN_OBS_TARGETS:
                    # target = container 또는 container/object_key (URL에 container 포함)
                    url = f"{base_url}/{target}"
                    t0 = time.time()
                    try:
                        resp = requests.head(url, headers=headers, timeout=10)
                        success = 200 <= resp.status_code < 400
                        obs_health_check_up.labels(region=region, target=target).set(
                            1 if success else 0
                        )
                    except Exception as e:
                        logger.debug(
                            "OBS health check [%s] %s failed: %s", region, target, e
                        )
                        obs_health_check_up.labels(region=region, target=target).set(0)
                        success = False
                    duration = time.time() - t0
                    obs_health_check_duration_seconds.labels(
                        region=region, target=target
                    ).set(round(duration, 4))
                    if not success:
                        logger.warning(
                            "OBS health check failed for [%s] %s (%.2fs)",
                            region,
                            target,
                            duration,
                        )

            exporter_scrape_duration.labels(collector="obs").observe(
                time.time() - start
            )
        except Exception as e:
            logger.error("OBS collector error: %s", e)
            exporter_scrape_errors.labels(collector="obs").inc()
            for region, base_url in base_list:
                for target in config.NHN_OBS_TARGETS:
                    obs_health_check_up.labels(region=region, target=target).set(0)
