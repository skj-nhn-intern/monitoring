"""Load Balancer Prometheus metrics."""

from prometheus_client import Gauge, Info

lb_info = Info("nhncloud_lb", "Load Balancer information", ["lb_id"])
# LB 통계 (OpenStack Octavia 호환 /v2.0/lbaas/loadbalancers/{id}/stats)
lb_stats_active_connections = Gauge(
    "nhncloud_lb_stats_active_connections",
    "Current active connections on the load balancer",
    ["lb_id", "lb_name"],
)
lb_stats_total_connections = Gauge(
    "nhncloud_lb_stats_total_connections",
    "Total connections handled by the load balancer",
    ["lb_id", "lb_name"],
)
lb_stats_bytes_in = Gauge(
    "nhncloud_lb_stats_bytes_in",
    "Total bytes received by the load balancer",
    ["lb_id", "lb_name"],
)
lb_stats_bytes_out = Gauge(
    "nhncloud_lb_stats_bytes_out",
    "Total bytes sent by the load balancer",
    ["lb_id", "lb_name"],
)
lb_stats_request_errors = Gauge(
    "nhncloud_lb_stats_request_errors",
    "Total request errors on the load balancer",
    ["lb_id", "lb_name"],
)

lb_status = Gauge(
    "nhncloud_lb_operating_status",
    "LB operating status (1=ONLINE,0=other)",
    ["lb_id", "lb_name"],
)
lb_provisioning = Gauge(
    "nhncloud_lb_provisioning_status",
    "LB provisioning status (1=ACTIVE,0=other)",
    ["lb_id", "lb_name"],
)
lb_admin_up = Gauge(
    "nhncloud_lb_admin_state_up",
    "LB admin state up",
    ["lb_id", "lb_name"],
)

pool_info = Info(
    "nhncloud_lb_pool",
    "Pool protocol and load balancing algorithm",
    ["pool_id", "pool_name", "lb_name"],
)
pool_status = Gauge(
    "nhncloud_lb_pool_operating_status",
    "Pool operating status (1=ONLINE,0=other)",
    ["pool_id", "pool_name", "lb_name"],
)
pool_member_count = Gauge(
    "nhncloud_lb_pool_member_total",
    "Total members in pool",
    ["pool_id", "pool_name", "lb_name"],
)
pool_healthy_member_count = Gauge(
    "nhncloud_lb_pool_member_healthy",
    "Healthy members in pool",
    ["pool_id", "pool_name", "lb_name"],
)
pool_unhealthy_member_count = Gauge(
    "nhncloud_lb_pool_member_unhealthy",
    "Unhealthy members in pool",
    ["pool_id", "pool_name", "lb_name"],
)

member_status = Gauge(
    "nhncloud_lb_member_operating_status",
    "Member operating status - only exported for currently running members (1=ONLINE, trend by scrape)",
    ["pool_id", "pool_name", "member_id", "member_address", "member_port", "lb_name"],
)
member_admin_up = Gauge(
    "nhncloud_lb_member_admin_state_up",
    "Member admin state - only exported for currently running members (1=up, trend by scrape)",
    ["pool_id", "pool_name", "member_id", "member_address", "member_port", "lb_name"],
)
member_weight = Gauge(
    "nhncloud_lb_member_weight",
    "Member weight - only exported for currently running members (trend by scrape)",
    ["pool_id", "pool_name", "member_id", "member_address", "member_port", "lb_name"],
)

healthmonitor_status = Gauge(
    "nhncloud_lb_healthmonitor_admin_state_up",
    "Health monitor admin state",
    ["hm_id", "pool_id"],
)
healthmonitor_delay = Gauge(
    "nhncloud_lb_healthmonitor_delay_seconds",
    "Health monitor delay",
    ["hm_id", "pool_id"],
)
healthmonitor_timeout = Gauge(
    "nhncloud_lb_healthmonitor_timeout_seconds",
    "Health monitor timeout",
    ["hm_id", "pool_id"],
)
healthmonitor_max_retries = Gauge(
    "nhncloud_lb_healthmonitor_max_retries",
    "Health monitor max retries",
    ["hm_id", "pool_id"],
)

listener_info = Info(
    "nhncloud_lb_listener",
    "Listener protocol, port and default pool",
    ["listener_id", "lb_name"],
)
listener_connection_limit = Gauge(
    "nhncloud_lb_listener_connection_limit",
    "Listener connection limit",
    ["listener_id", "protocol", "port", "lb_name"],
)
listener_cert_expire_days = Gauge(
    "nhncloud_lb_listener_cert_expire_days",
    "Days until TLS cert expiry",
    ["listener_id", "lb_name"],
)
