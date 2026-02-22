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
    - 4xx(401, 404 등)는 재시도하지 않음 (클라이언트 오류는 재시도해도 동일).
    - retry_connection_errors=False: DNS/연결 실패 시 재시도 없이 즉시 raise (로그 스팸 방지).
    """
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            # 4xx는 재시도 없이 즉시 raise (LB 401, CDN 404 등 로그 스팸 방지, 수집기에서 한 번만 로그)
            if e.response is not None and 400 <= e.response.status_code < 500:
                raise
            logger.warning("GET %s attempt %d failed: %s", url, attempt + 1, e)
            if attempt == 2:
                raise
            time.sleep(2**attempt)
        except requests.exceptions.RequestException as e:
            # DNS/연결 오류 시 재시도 스킵 (RDS 등). MaxRetryError 등은 메시지로 판단
            skip_retry = not retry_connection_errors and (
                isinstance(
                    e,
                    (requests.exceptions.ConnectionError, requests.exceptions.Timeout),
                )
                or "resolve" in str(e).lower()
                or "max retries" in str(e).lower()
            )
            if skip_retry:
                raise
            logger.warning("GET %s attempt %d failed: %s", url, attempt + 1, e)
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("Unreachable")


def map_status(value: Optional[str], mapping: dict, default: int = 0) -> int:
    """Map string status to numeric code (case-insensitive)."""
    return mapping.get((value or "").upper(), default)
