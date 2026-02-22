"""
Object Storage (OBS) health check – 공개 URL만.

OBS_PUBLIC_HEALTH_CHECK_URLS에 브라우저/curl로 여는 전체 URL을 넣으면
인증 없이 HEAD(또는 GET) 요청으로 2xx면 up.
"""

import logging
import time
from urllib.parse import urlparse

import requests

from nhncloud_exporter import config
from nhncloud_exporter.metrics import (
    exporter_scrape_duration,
    obs_health_check_duration_seconds,
    obs_health_check_up,
)

logger = logging.getLogger("nhncloud-exporter")


def _target_label_from_url(url: str) -> str:
    """공개 URL용 짧은 target 라벨 (호스트 + 경로 첫 단계)."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc or "unknown"
        path = (parsed.path or "").strip("/")
        first = path.split("/")[0] if path else ""
        return f"{host}/{first}" if first else host
    except Exception:
        return "unknown"


class OBSCollector:
    """공개 URL만 HEAD(또는 GET)로 헬스 체크."""

    def collect(self) -> None:
        if not config.OBS_PUBLIC_HEALTH_CHECK_URLS:
            return

        start = time.time()
        for url in config.OBS_PUBLIC_HEALTH_CHECK_URLS:
            target_label = _target_label_from_url(url)
            t0 = time.time()
            try:
                resp = requests.head(url, timeout=10)
                if resp.status_code == 405:
                    resp = requests.get(url, timeout=10, stream=True)
                    if resp.raw:
                        resp.raw.close()
                success = 200 <= resp.status_code < 400
                obs_health_check_up.labels(region="public", target=target_label).set(
                    1 if success else 0
                )
            except Exception as e:
                logger.debug("OBS public check %s failed: %s", target_label, e)
                obs_health_check_up.labels(region="public", target=target_label).set(0)
                success = False
            duration = time.time() - t0
            obs_health_check_duration_seconds.labels(
                region="public", target=target_label
            ).set(round(duration, 4))
            if not success:
                logger.warning(
                    "OBS health check failed for %s (%.2fs)", target_label, duration
                )

        exporter_scrape_duration.labels(collector="obs").observe(time.time() - start)
