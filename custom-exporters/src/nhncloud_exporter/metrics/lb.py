"""Load Balancer Prometheus metrics."""

from prometheus_client import Gauge, Info

lb_info = Info("nhncloud_lb", "Load Balancer information", ["lb_id"])
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
    "Member operating status (1=ONLINE,0=other)",
    ["pool_id", "pool_name", "member_id", "member_address", "member_port", "lb_name"],
)
member_admin_up = Gauge(
    "nhncloud_lb_member_admin_state_up",
    "Member admin state",
    ["pool_id", "pool_name", "member_id", "member_address", "member_port", "lb_name"],
)
member_weight = Gauge(
    "nhncloud_lb_member_weight",
    "Member weight",
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
