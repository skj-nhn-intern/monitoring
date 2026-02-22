"""Environment-based configuration for NHN Cloud Exporter."""

import os
import logging

# Identity
NHN_AUTH_URL = os.getenv(
    "NHN_AUTH_URL",
    "https://api-identity-infrastructure.nhncloudservice.com/v2.0/tokens",
)
NHN_TENANT_ID = os.getenv("NHN_TENANT_ID", "")
NHN_USERNAME = os.getenv("NHN_USERNAME", "")
NHN_PASSWORD = os.getenv("NHN_PASSWORD", "")

# Network (LB). 지정 시 해당 LB만 수집 (pool/member/listener 등). 미설정 시 전체 수집.
NHN_NETWORK_ENDPOINT = os.getenv("NHN_NETWORK_ENDPOINT", "")
# LB 전용 OAuth2 (Keystone 401 시 사용). 콘솔 > 이메일 > API 보안 설정 > User Access Key ID / Secret 발급.
NHN_LB_OAUTH2_KEY = os.getenv("NHN_LB_OAUTH2_KEY", "")
NHN_LB_OAUTH2_SECRET = os.getenv("NHN_LB_OAUTH2_SECRET", "")
NHN_OAUTH2_TOKEN_URL = os.getenv(
    "NHN_OAUTH2_TOKEN_URL",
    "https://oauth.api.nhncloudservice.com/oauth2/token/create",
)
NHN_LB_IDS = [i.strip() for i in os.getenv("NHN_LB_IDS", "").split(",") if i.strip()]
LB_NAMES = [n.strip() for n in os.getenv("NHN_LB_NAMES", "").split(",") if n.strip()]
LB_POOL_IDS = [p.strip() for p in os.getenv("NHN_LB_POOL_IDS", "").split(",") if p.strip()]

# CDN
NHN_CDN_APPKEY = os.getenv("NHN_CDN_APPKEY", "")
NHN_CDN_SECRETKEY = os.getenv("NHN_CDN_SECRETKEY", "")
# 문서 기준 CDN Public API 도메인은 리전 없음. kr1-cdn 사용 시 statistics API 404 발생 가능.
NHN_CDN_API_BASE = os.getenv(
    "NHN_CDN_API_BASE",
    "https://cdn.api.nhncloudservice.com",
)

# RDS
NHN_RDS_APPKEY = os.getenv("NHN_RDS_APPKEY", "")
NHN_RDS_SECRETKEY = os.getenv("NHN_RDS_SECRETKEY", "")
NHN_RDS_API_BASE = os.getenv(
    "NHN_RDS_API_BASE",
    "https://kr1-api-mysql.rds.nhncloudservice.com",
)
# RDS 수집 간격(초). DB 상태/백업은 자주 안 바뀌므로 기본 300(5분). DNS 오류 시 로그 스팸 완화
RDS_SCRAPE_INTERVAL = int(os.getenv("RDS_SCRAPE_INTERVAL", "300"))

# Object Storage (OBS) – API health check, 30s interval, multiple targets (replicated objects)
# URL 형식: base + /v1/AUTH_tenant_id + / + target → target은 반드시 container 또는 container/object_key
NHN_OBS_API_URL = os.getenv(
    "NHN_OBS_API_URL",
    "",
).rstrip("/")
# Multiple OBS API URLs (리전 무관): 쉼표 구분. 미설정 시 NHN_OBS_API_URL 1개 또는 토큰 카탈로그 사용
NHN_OBS_API_URLS = [
    u.strip().rstrip("/")
    for u in os.getenv("NHN_OBS_API_URLS", "").split(",")
    if u.strip()
]
# Comma-separated targets: container or container/object_key (e.g. "photo,bucket2,bucket2/backup.dat")
NHN_OBS_TARGETS = [
    t.strip()
    for t in os.getenv("NHN_OBS_TARGETS", "").split(",")
    if t.strip()
]
# 공개 URL만 직접 체크 (API/토큰 불필요). 쉼표 구분 전체 URL. 브라우저에서 여는 그 주소 그대로 넣으면 됨.
OBS_PUBLIC_HEALTH_CHECK_URLS = [
    u.strip()
    for u in os.getenv("OBS_PUBLIC_HEALTH_CHECK_URLS", "").split(",")
    if u.strip()
]
OBS_HEALTH_CHECK_INTERVAL = int(os.getenv("OBS_HEALTH_CHECK_INTERVAL", "30"))

# Exporter
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9101"))
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL", "60"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
# Disable specific collectors (comma-separated: loadbalancer, cdn, rds) to avoid 401/404/DNS errors
DISABLE_COLLECTORS = {
    s.strip().lower()
    for s in os.getenv("NHN_DISABLE_COLLECTORS", "").split(",")
    if s.strip()
}


def setup_logging() -> logging.Logger:
    """Configure logging and return the exporter logger."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return logging.getLogger("nhncloud-exporter")
