"""
CDN collector – 외부 URL 상태만 체크.

API 호출 없이 NHN_CDN_HEALTH_CHECK_URLS에 설정한 공개 URL에 요청해서 응답 여부만 확인.
"""

import logging
import time
from urllib.parse import urlparse

import requests

from nhncloud_exporter import config
from nhncloud_exporter.metrics import (
    cdn_health_check_duration_seconds,
    cdn_health_check_up,
    exporter_scrape_duration,
)

logger = logging.getLogger("nhncloud-exporter")


def _target_label_from_url(url: str) -> str:
    """URL에서 target 라벨 (호스트 + 경로 첫 단계)."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc or "unknown"
        path = (parsed.path or "").strip("/")
        first = path.split("/")[0] if path else ""
        return f"{host}/{first}" if first else host
    except Exception:
        return "unknown"


class CDNCollector:
    """외부 URL에 요청해서 CDN 상태만 체크."""

    def collect(self) -> None:
        if not config.NHN_CDN_HEALTH_CHECK_URLS:
            logger.debug("CDN collector skipped: no NHN_CDN_HEALTH_CHECK_URLS")
            return

        start = time.time()
        for url in config.NHN_CDN_HEALTH_CHECK_URLS:
            target = _target_label_from_url(url)
            t0 = time.time()
            try:
                resp = requests.head(url, timeout=10)
                if resp.status_code == 405:
                    resp = requests.get(url, timeout=10, stream=True)
                    if resp.raw:
                        resp.raw.close()
                success = 200 <= resp.status_code < 400
                cdn_health_check_up.labels(target=target).set(1 if success else 0)
            except Exception as e:
                logger.debug("CDN health check %s failed: %s", target, e)
                cdn_health_check_up.labels(target=target).set(0)
                success = False
            duration = time.time() - t0
            cdn_health_check_duration_seconds.labels(target=target).set(
                round(duration, 4)
            )
            if not success:
                logger.warning(
                    "CDN health check failed for %s (%.2fs)", target, duration
                )
        exporter_scrape_duration.labels(collector="cdn").observe(time.time() - start)
