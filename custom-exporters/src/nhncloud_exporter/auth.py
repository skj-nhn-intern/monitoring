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
        url = config.NHN_OAUTH2_TOKEN_URL
        logger.info("LB token: requesting OAuth2 token from %s", url)
        basic = base64.b64encode(f"{key}:{secret}".encode()).decode()
        try:
            resp = requests.post(
                url,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {basic}",
                },
                data={"grant_type": "client_credentials"},
                timeout=15,
            )
        except requests.exceptions.ConnectionError as e:
            logger.error(
                "LB OAuth2: 연결 실패 url=%s – %s (URL/네트워크 확인)",
                url,
                e,
            )
            raise
        except requests.exceptions.Timeout:
            logger.error("LB OAuth2: 타임아웃 url=%s", url)
            raise

        body_preview = (resp.text or resp.reason or "")[:500].replace("\n", " ")
        if resp.status_code == 401:
            logger.warning(
                "LB OAuth2 401 인증 실패 url=%s – response: %s (Key/Secret 또는 URL 확인)",
                url,
                body_preview,
            )
        elif resp.status_code >= 400:
            logger.warning(
                "LB OAuth2 HTTP %s url=%s – response: %s",
                resp.status_code,
                url,
                body_preview,
            )
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            logger.error(
                "LB OAuth2: 응답이 JSON이 아님 url=%s – body: %s",
                url,
                body_preview[:200],
            )
            raise
        if "access_token" not in data:
            logger.error("LB OAuth2: 응답에 access_token 없음 – keys: %s", list(data.keys()))
            raise ValueError("OAuth2 response missing access_token")
        self._token = data["access_token"]
        expires_in = int(data.get("expires_in", 86400))
        self._expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        logger.info("LB OAuth2 token refreshed, expires at %s", self._expires_at)


oauth2_lb_mgr: Optional[OAuth2TokenManager] = None


def get_lb_token() -> str:
    """LB API용 토큰. Keystone이 설정돼 있으면 Keystone(Network API 호환), 없으면 OAuth2."""
    use_keystone = (
        config.NHN_TENANT_ID and config.NHN_USERNAME and config.NHN_PASSWORD
    )
    if use_keystone:
        return token_mgr.get_token()
    if config.NHN_LB_OAUTH2_KEY and config.NHN_LB_OAUTH2_SECRET:
        global oauth2_lb_mgr
        if oauth2_lb_mgr is None:
            oauth2_lb_mgr = OAuth2TokenManager()
        return oauth2_lb_mgr.get_token()
    logger.error(
        "LB 토큰 발급 불가: Keystone(NHN_TENANT_ID, NHN_USERNAME, NHN_PASSWORD) 또는 "
        "OAuth2(NHN_LB_OAUTH2_KEY, NHN_LB_OAUTH2_SECRET) 중 하나를 설정해야 합니다. "
        "Network API는 Keystone 토큰을 권장합니다."
    )
    raise RuntimeError(
        "LB credentials not set. Set NHN_TENANT_ID+NHN_USERNAME+NHN_PASSWORD or NHN_LB_OAUTH2_KEY+NHN_LB_OAUTH2_SECRET"
    )


def is_lb_oauth2() -> bool:
    """LB가 이번 요청에서 OAuth2 토큰을 쓰면 True. Keystone이 설정돼 있으면 False(Network API는 Keystone만 인식)."""
    use_keystone = (
        config.NHN_TENANT_ID and config.NHN_USERNAME and config.NHN_PASSWORD
    )
    return bool(
        config.NHN_LB_OAUTH2_KEY
        and config.NHN_LB_OAUTH2_SECRET
        and not use_keystone
    )


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
        url = config.NHN_AUTH_URL
        logger.info("LB token: requesting Keystone token from %s", url)
        try:
            resp = requests.post(url, json=body, timeout=15)
        except requests.exceptions.ConnectionError as e:
            logger.error(
                "LB Keystone: 연결 실패 url=%s – %s (NHN_AUTH_URL/네트워크 확인)",
                url,
                e,
            )
            raise
        except requests.exceptions.Timeout:
            logger.error("LB Keystone: 타임아웃 url=%s", url)
            raise

        body_preview = (resp.text or resp.reason or "")[:500].replace("\n", " ")
        if resp.status_code == 401:
            logger.warning(
                "LB Keystone 401 인증 실패 url=%s – response: %s (TENANT_ID/USERNAME/PASSWORD(API 비밀번호) 확인)",
                url,
                body_preview,
            )
        elif resp.status_code >= 400:
            logger.warning(
                "LB Keystone HTTP %s url=%s – response: %s",
                resp.status_code,
                url,
                body_preview,
            )
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            logger.error(
                "LB Keystone: 응답이 JSON이 아님 url=%s – body: %s",
                url,
                body_preview[:200],
            )
            raise
        try:
            access = data["access"]
            self._token = access["token"]["id"]
            expires_str = access["token"]["expires"]
            self._expires_at = datetime.fromisoformat(
                expires_str.replace("Z", "+00:00")
            )
            self._service_catalog = {
                s["type"]: s for s in access.get("serviceCatalog", [])
            }
            logger.info("Token refreshed, expires at %s", self._expires_at)
        except KeyError as e:
            logger.error(
                "LB Keystone: 응답 구조 예상과 다름 (access.token 등) – keys: %s, error: %s",
                list(data.keys()) if isinstance(data, dict) else type(data).__name__,
                e,
            )
            raise

    @property
    def service_catalog(self) -> dict:
        return self._service_catalog


# Singleton used by LB collector (OpenStack API)
token_mgr = TokenManager()
