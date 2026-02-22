"""CDN Prometheus metrics – 외부 URL 상태 체크만."""

from prometheus_client import Gauge

cdn_health_check_up = Gauge(
    "nhncloud_cdn_health_check_up",
    "CDN 외부 URL 상태 (1=응답 정상, 0=실패)",
    ["target"],
)
cdn_health_check_duration_seconds = Gauge(
    "nhncloud_cdn_health_check_duration_seconds",
    "CDN 외부 URL 요청 소요 시간(초)",
    ["target"],
)
