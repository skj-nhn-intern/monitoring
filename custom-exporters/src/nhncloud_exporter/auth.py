"""NHN Cloud Identity (Keystone v2) and OAuth2 token managers."""

import base64
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from nhncloud_exporter import config

logger = logging.getLogger("nhncloud-exporter")


class OAuth2TokenManager:
    """OAuth2 token for LB/Network API (User Access Key ID + Secret). Keystone 401 시 대안."""

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._expires_at: Optional[datetime] = None
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
            self._refresh()
            return self._token  # type: ignore[return-value]

    def _refresh(self) -> None:
        key = config.NHN_LB_OAUTH2_KEY
        secret = config.NHN_LB_OAUTH2_SECRET
        if not key or not secret:
            raise RuntimeError("NHN_LB_OAUTH2_KEY and NHN_LB_OAUTH2_SECRET required")
        basic = base64.b64encode(f"{key}:{secret}".encode()).decode()
        resp = requests.post(
            config.NHN_OAUTH2_TOKEN_URL,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {basic}",
            },
            data={"grant_type": "client_credentials"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        expires_in = int(data.get("expires_in", 86400))
        self._expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        logger.info("LB OAuth2 token refreshed, expires at %s", self._expires_at)


oauth2_lb_mgr: Optional[OAuth2TokenManager] = None


def get_lb_token() -> str:
    """LB API용 토큰. NHN_LB_OAUTH2_KEY가 있으면 OAuth2, 없으면 Keystone."""
    if config.NHN_LB_OAUTH2_KEY and config.NHN_LB_OAUTH2_SECRET:
        global oauth2_lb_mgr
        if oauth2_lb_mgr is None:
            oauth2_lb_mgr = OAuth2TokenManager()
        return oauth2_lb_mgr.get_token()
    return token_mgr.get_token()


def is_lb_oauth2() -> bool:
    """LB가 OAuth2 사용 중이면 True (헤더 추가 시 사용)."""
    return bool(config.NHN_LB_OAUTH2_KEY and config.NHN_LB_OAUTH2_SECRET)


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
