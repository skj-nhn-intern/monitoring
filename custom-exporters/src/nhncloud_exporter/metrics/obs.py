"""Object Storage (OBS) health check Prometheus metrics."""

from prometheus_client import Gauge

# Health check result per region and target (container or container/object_key)
obs_health_check_up = Gauge(
    "nhn_obs_health_check_up",
    "Object Storage API health check result (1=up, 0=down)",
    ["region", "target"],
)
obs_health_check_duration_seconds = Gauge(
    "nhn_obs_health_check_duration_seconds",
    "Object Storage API health check duration in seconds",
    ["region", "target"],
)
