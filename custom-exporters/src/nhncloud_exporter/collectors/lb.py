"""
Load Balancer collector.

Collects LB, Pool, Member, HealthMonitor, Listener metrics.
API: OpenStack LBaaS v2.0 compatible (NHN Cloud Network API).
"""

import logging
from datetime import datetime, timezone

from nhncloud_exporter import config
from nhncloud_exporter.auth import token_mgr
from nhncloud_exporter.utils import api_get
from nhncloud_exporter.metrics import (
    exporter_scrape_errors,
    lb_admin_up,
    lb_provisioning,
    lb_status,
    listener_cert_expire_days,
    listener_connection_limit,
    member_admin_up,
    member_status,
    member_weight,
    pool_healthy_member_count,
    pool_member_count,
    pool_status,
    pool_unhealthy_member_count,
    healthmonitor_delay,
    healthmonitor_max_retries,
    healthmonitor_status,
    healthmonitor_timeout,
)

logger = logging.getLogger("nhncloud-exporter")


class LoadBalancerCollector:
    """Collects Load Balancer, Pool, Member, HealthMonitor, Listener metrics."""

    def collect(self) -> None:
        if not config.NHN_NETWORK_ENDPOINT:
            logger.debug("LB collector skipped: no NHN_NETWORK_ENDPOINT")
            return

        headers = {"X-Auth-Token": token_mgr.get_token()}
        base = config.NHN_NETWORK_ENDPOINT.rstrip("/")

        try:
            self._collect_loadbalancers(base, headers)
            self._collect_pools_and_members(base, headers)
            self._collect_healthmonitors(base, headers)
            self._collect_listeners(base, headers)
        except Exception as e:
            logger.error("LB collector error: %s", e)
            exporter_scrape_errors.labels(collector="loadbalancer").inc()

    def _collect_loadbalancers(self, base: str, headers: dict) -> None:
        lb_data = api_get(f"{base}/v2.0/lbaas/loadbalancers", headers)
        for lb in lb_data.get("loadbalancers", []):
            lb_id = lb["id"]
            lb_name = lb.get("name", lb_id[:8])
            lb_status.labels(lb_id=lb_id, lb_name=lb_name).set(
                1 if lb.get("operating_status", "").upper() == "ONLINE" else 0
            )
            lb_provisioning.labels(lb_id=lb_id, lb_name=lb_name).set(
                1 if lb.get("provisioning_status", "").upper() == "ACTIVE" else 0
            )
            lb_admin_up.labels(lb_id=lb_id, lb_name=lb_name).set(
                1 if lb.get("admin_state_up", False) else 0
            )

    def _collect_pools_and_members(self, base: str, headers: dict) -> None:
        pools_data = api_get(f"{base}/v2.0/lbaas/pools", headers)
        for pool in pools_data.get("pools", []):
            pool_id = pool["id"]
            pool_name = pool.get("name", pool_id[:8])
            parent_lb_name = ""
            for lb_ref in pool.get("loadbalancers", []):
                parent_lb_name = lb_ref.get("id", "")[:8]
                break

            pool_status.labels(
                pool_id=pool_id, pool_name=pool_name, lb_name=parent_lb_name
            ).set(1 if pool.get("operating_status", "").upper() == "ONLINE" else 0)

            members_data = api_get(
                f"{base}/v2.0/lbaas/pools/{pool_id}/members", headers
            )
            members = members_data.get("members", [])
            total = len(members)
            healthy = sum(
                1
                for m in members
                if m.get("operating_status", "").upper() == "ONLINE"
            )
            unhealthy = total - healthy

            pool_member_count.labels(
                pool_id=pool_id, pool_name=pool_name, lb_name=parent_lb_name
            ).set(total)
            pool_healthy_member_count.labels(
                pool_id=pool_id, pool_name=pool_name, lb_name=parent_lb_name
            ).set(healthy)
            pool_unhealthy_member_count.labels(
                pool_id=pool_id, pool_name=pool_name, lb_name=parent_lb_name
            ).set(unhealthy)

            for m in members:
                labels = {
                    "pool_id": pool_id,
                    "pool_name": pool_name,
                    "member_id": m["id"],
                    "member_address": m.get("address", ""),
                    "member_port": str(m.get("protocol_port", "")),
                    "lb_name": parent_lb_name,
                }
                member_status.labels(**labels).set(
                    1 if m.get("operating_status", "").upper() == "ONLINE" else 0
                )
                member_admin_up.labels(**labels).set(
                    1 if m.get("admin_state_up", False) else 0
                )
                member_weight.labels(**labels).set(m.get("weight", 1))

    def _collect_healthmonitors(self, base: str, headers: dict) -> None:
        hm_data = api_get(f"{base}/v2.0/lbaas/healthmonitors", headers)
        for hm in hm_data.get("healthmonitors", []):
            hm_id = hm["id"]
            hm_pools = hm.get("pools", [])
            hm_pool_id = hm_pools[0]["id"] if hm_pools else ""
            healthmonitor_status.labels(hm_id=hm_id, pool_id=hm_pool_id).set(
                1 if hm.get("admin_state_up", False) else 0
            )
            healthmonitor_delay.labels(hm_id=hm_id, pool_id=hm_pool_id).set(
                hm.get("delay", 0)
            )
            healthmonitor_timeout.labels(hm_id=hm_id, pool_id=hm_pool_id).set(
                hm.get("timeout", 0)
            )
            healthmonitor_max_retries.labels(
                hm_id=hm_id, pool_id=hm_pool_id
            ).set(hm.get("max_retries", 0))

    def _collect_listeners(self, base: str, headers: dict) -> None:
        listeners_data = api_get(f"{base}/v2.0/lbaas/listeners", headers)
        for li in listeners_data.get("listeners", []):
            li_id = li["id"]
            protocol = li.get("protocol", "")
            port = str(li.get("protocol_port", ""))
            parent = ""
            for lb_ref in li.get("loadbalancers", []):
                parent = lb_ref.get("id", "")[:8]
                break
            listener_connection_limit.labels(
                listener_id=li_id, protocol=protocol, port=port, lb_name=parent
            ).set(li.get("connection_limit", 0))

            cert_expire = li.get("cert_expire_date")
            if cert_expire:
                try:
                    exp_dt = datetime.fromisoformat(
                        cert_expire.replace("Z", "+00:00")
                    )
                    days = (exp_dt - datetime.now(timezone.utc)).days
                    listener_cert_expire_days.labels(
                        listener_id=li_id, lb_name=parent
                    ).set(days)
                except Exception:
                    pass
