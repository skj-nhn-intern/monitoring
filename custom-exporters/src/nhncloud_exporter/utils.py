"""HTTP and mapping helpers."""

import logging
import time
from typing import Any, Optional

import requests

logger = logging.getLogger("nhncloud-exporter")


def api_get(
    url: str,
    headers: Optional[dict] = None,
    timeout: int = 30,
    retry_connection_errors: bool = True,
) -> Any:
    """GET request with retry (3 attempts, exponential backoff).
    retry_connection_errors=False: DNS/연결 실패 시 재시도 없이 즉시 raise (로그 스팸 방지).
    """
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            is_connection_error = isinstance(
                e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
            )
            if is_connection_error and not retry_connection_errors:
                raise
            logger.warning("GET %s attempt %d failed: %s", url, attempt + 1, e)
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("Unreachable")


def map_status(value: Optional[str], mapping: dict, default: int = 0) -> int:
    """Map string status to numeric code (case-insensitive)."""
    return mapping.get((value or "").upper(), default)
