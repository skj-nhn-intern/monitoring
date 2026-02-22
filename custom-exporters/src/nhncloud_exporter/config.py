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

# Network (LB)
NHN_NETWORK_ENDPOINT = os.getenv("NHN_NETWORK_ENDPOINT", "")
LB_POOL_IDS = [p.strip() for p in os.getenv("NHN_LB_POOL_IDS", "").split(",") if p.strip()]
LB_NAMES = [n.strip() for n in os.getenv("NHN_LB_NAMES", "").split(",") if n.strip()]

# CDN
NHN_CDN_APPKEY = os.getenv("NHN_CDN_APPKEY", "")
NHN_CDN_SECRETKEY = os.getenv("NHN_CDN_SECRETKEY", "")
NHN_CDN_API_BASE = os.getenv(
    "NHN_CDN_API_BASE",
    "https://kr1-cdn.api.nhncloudservice.com",
)

# RDS
NHN_RDS_APPKEY = os.getenv("NHN_RDS_APPKEY", "")
NHN_RDS_SECRETKEY = os.getenv("NHN_RDS_SECRETKEY", "")
NHN_RDS_API_BASE = os.getenv(
    "NHN_RDS_API_BASE",
    "https://kr1-api-mysql.rds.nhncloudservice.com",
)

# Object Storage (OBS) – API health check, 30s interval, multiple targets (replicated objects)
NHN_OBS_API_URL = os.getenv(
    "NHN_OBS_API_URL",
    "",
).rstrip("/")
# Comma-separated targets: container or container/object_key (e.g. "bucket1,bucket2/backup.dat")
NHN_OBS_TARGETS = [
    t.strip()
    for t in os.getenv("NHN_OBS_TARGETS", "").split(",")
    if t.strip()
]
OBS_HEALTH_CHECK_INTERVAL = int(os.getenv("OBS_HEALTH_CHECK_INTERVAL", "30"))

# Exporter
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9101"))
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL", "60"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def setup_logging() -> logging.Logger:
    """Configure logging and return the exporter logger."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return logging.getLogger("nhncloud-exporter")
