"""CDN Prometheus metrics."""

from prometheus_client import Gauge

cdn_distribution_status = Gauge(
    "nhncloud_cdn_distribution_status",
    "CDN distribution status (1=OPEN,2=OPENING,3=CLOSED,4=ERROR,0=UNKNOWN)",
    ["domain", "region", "description"],
)
cdn_distribution_cache_type = Gauge(
    "nhncloud_cdn_distribution_cache_type",
    "Cache type (1=NO_STORE,2=BYPASS,3=ORIGIN,0=UNKNOWN)",
    ["domain"],
)
cdn_distribution_default_max_age = Gauge(
    "nhncloud_cdn_distribution_default_max_age_seconds",
    "Default Max-Age for CDN cache",
    ["domain"],
)
cdn_root_path_redirect_enabled = Gauge(
    "nhncloud_cdn_root_redirect_enabled",
    "Root path access control enabled",
    ["domain"],
)
cdn_root_path_redirect_status_code = Gauge(
    "nhncloud_cdn_root_redirect_status_code",
    "Root path redirect status code (e.g. 301, 302)",
    ["domain", "redirect_path"],
)
cdn_origin_http_downgrade = Gauge(
    "nhncloud_cdn_origin_http_downgrade",
    "Origin HTTP protocol downgrade enabled",
    ["domain"],
)
cdn_large_file_optimization = Gauge(
    "nhncloud_cdn_large_file_optimization",
    "Large file optimization enabled",
    ["domain"],
)
cdn_use_origin_cache_control = Gauge(
    "nhncloud_cdn_use_origin_cache_control",
    "Use origin cache-control header",
    ["domain"],
)
cdn_callback_configured = Gauge(
    "nhncloud_cdn_callback_configured",
    "CDN callback URL configured (1=yes,0=no)",
    ["domain"],
)
cdn_referrer_type = Gauge(
    "nhncloud_cdn_referrer_type",
    "Referrer type (1=BLACKLIST,2=WHITELIST,0=NONE)",
    ["domain"],
)
cdn_allow_post = Gauge("nhncloud_cdn_allow_post", "Allow POST requests", ["domain"])
cdn_allow_put = Gauge("nhncloud_cdn_allow_put", "Allow PUT requests", ["domain"])
cdn_allow_delete = Gauge("nhncloud_cdn_allow_delete", "Allow DELETE requests", ["domain"])
cdn_cert_status = Gauge(
    "nhncloud_cdn_certificate_status",
    "Certificate status code",
    ["domain", "dns_name"],
)
cdn_cert_expire_days = Gauge(
    "nhncloud_cdn_certificate_expire_days",
    "Days until certificate renewal end",
    ["domain", "dns_name"],
)

cdn_stat_bandwidth = Gauge(
    "nhncloud_cdn_bandwidth_bps", "CDN bandwidth in bps", ["domain"]
)
cdn_stat_transfer = Gauge(
    "nhncloud_cdn_data_transferred_bytes",
    "CDN data transferred bytes",
    ["domain"],
)
cdn_stat_request_hit = Gauge(
    "nhncloud_cdn_request_hit_count",
    "CDN cache hit requests",
    ["domain"],
)
cdn_stat_request_miss = Gauge(
    "nhncloud_cdn_request_miss_count",
    "CDN cache miss requests",
    ["domain"],
)
cdn_stat_request_bypass = Gauge(
    "nhncloud_cdn_request_bypass_count",
    "CDN cache bypass requests",
    ["domain"],
)
cdn_stat_hit_ratio = Gauge(
    "nhncloud_cdn_cache_hit_ratio",
    "CDN cache hit ratio (0.0-1.0)",
    ["domain"],
)

cdn_http_2xx = Gauge("nhncloud_cdn_http_2xx_count", "CDN 2xx responses", ["domain"])
cdn_http_3xx = Gauge(
    "nhncloud_cdn_http_3xx_count",
    "CDN 3xx responses (redirect)",
    ["domain"],
)
cdn_http_4xx = Gauge("nhncloud_cdn_http_4xx_count", "CDN 4xx responses", ["domain"])
cdn_http_5xx = Gauge("nhncloud_cdn_http_5xx_count", "CDN 5xx responses", ["domain"])
