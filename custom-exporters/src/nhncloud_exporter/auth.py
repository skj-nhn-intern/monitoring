"""NHN Cloud Identity (Keystone v2) token manager."""

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from nhncloud_exporter import config

logger = logging.getLogger("nhncloud-exporter")


class TokenManager:
    """Token manager with auto-refresh (refresh 5 minutes before expiry)."""

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._expires_at: Optional[datetime] = None
        self._service_catalog: dict = {}
        self._lock = threading.Lock()

    def get_token(self) -> str:
        with self._lock:
            if (
                self._token
                and self._expires_at
                and datetime.now(timezone.utc)
                < self._expires_at - timedelta(minutes=5)
            ):
                return self._token
            self._refresh_token()
            return self._token  # type: ignore[return-value]

    def _refresh_token(self) -> None:
        body = {
            "auth": {
                "tenantId": config.NHN_TENANT_ID,
                "passwordCredentials": {
                    "username": config.NHN_USERNAME,
                    "password": config.NHN_PASSWORD,
                },
            }
        }
        try:
            resp = requests.post(config.NHN_AUTH_URL, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()["access"]
            self._token = data["token"]["id"]
            expires_str = data["token"]["expires"]
            self._expires_at = datetime.fromisoformat(
                expires_str.replace("Z", "+00:00")
            )
            self._service_catalog = {
                s["type"]: s for s in data.get("serviceCatalog", [])
            }
            logger.info("Token refreshed, expires at %s", self._expires_at)
        except Exception as e:
            logger.error("Token refresh failed: %s", e)
            raise

    @property
    def service_catalog(self) -> dict:
        return self._service_catalog


# Singleton used by LB collector (OpenStack API)
token_mgr = TokenManager()
