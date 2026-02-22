"""
Load Balancer collector.

Collects LB, Pool, Member, HealthMonitor, Listener metrics.
API: OpenStack LBaaS v2.0 compatible (NHN Cloud Network API).
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from nhncloud_exporter import config
from nhncloud_exporter.auth import get_lb_token, is_lb_oauth2
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


def _allowed_lb_ids(lb_list: list) -> Optional[set]:
    """NHN_LB_IDS 또는 LB_NAMES가 있으면 해당 LB만, 없으면 None(전체)."""
    if not config.NHN_LB_IDS and not config.LB_NAMES:
        return None
    want_ids = set(config.NHN_LB_IDS)
    want_names = set(config.LB_NAMES)
    allowed = set()
    for lb in lb_list:
        lb_id = lb.get("id", "")
        lb_name = lb.get("name", "")
        if lb_id in want_ids or lb_name in want_names:
            allowed.add(lb_id)
    return allowed if (want_ids or want_names) else None


class LoadBalancerCollector:
    """Collects Load Balancer, Pool, Member, HealthMonitor, Listener metrics. NHN_LB_IDS/LB_NAMES 지정 시 해당 LB만 수집."""

    def collect(self) -> None:
        if not config.NHN_NETWORK_ENDPOINT:
            logger.debug("LB collector skipped: no NHN_NETWORK_ENDPOINT")
            return

        token = get_lb_token()
        headers = {"X-Auth-Token": token}
        if is_lb_oauth2():
            headers["Authorization"] = f"Bearer {token}"
        if config.NHN_TENANT_ID and not is_lb_oauth2():
            headers["X-Tenant-Id"] = config.NHN_TENANT_ID
        base = config.NHN_NETWORK_ENDPOINT.rstrip("/")

        try:
            lb_data = api_get(f"{base}/v2.0/lbaas/loadbalancers", headers)
            lb_list = lb_data.get("loadbalancers", [])
            allowed_lb_ids = _allowed_lb_ids(lb_list)

            self._collect_loadbalancers(lb_list, allowed_lb_ids)
            allowed_pool_ids = self._collect_pools_and_members(base, headers, lb_list, allowed_lb_ids)
            self._collect_healthmonitors(base, headers, allowed_pool_ids)
            self._collect_listeners(base, headers, allowed_lb_ids)
        except Exception as e:
            err = str(e)
            if "401" in err:
                logger.warning(
                    "LB API 401. Try OAuth2: set NHN_LB_OAUTH2_KEY + NHN_LB_OAUTH2_SECRET (Console > API Security > User Access Key). "
                    "Else check NHN_TENANT_ID, NHN_USERNAME, NHN_PASSWORD (API password)."
                )
                resp = getattr(e, "response", None)
                if resp is not None and hasattr(resp, "text") and resp.text:
                    logger.debug("LB API 401 response: %s", resp.text[:500])
            else:
                logger.error("LB collector error: %s", e)
            exporter_scrape_errors.labels(collector="loadbalancer").inc()

    def _collect_loadbalancers(self, lb_list: list, allowed_lb_ids: Optional[set]) -> None:
        for lb in lb_list:
            lb_id = lb["id"]
            if allowed_lb_ids is not None and lb_id not in allowed_lb_ids:
                continue
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

    def _collect_pools_and_members(
        self, base: str, headers: dict, lb_list: list, allowed_lb_ids: Optional[set]
    ) -> set:
        """수집한 pool id 집합 반환 (healthmonitor 필터용)."""
        pools_data = api_get(f"{base}/v2.0/lbaas/pools", headers)
        allowed_pool_ids = set()
        for pool in pools_data.get("pools", []):
            pool_lb_id = ""
            for lb_ref in pool.get("loadbalancers", []):
                pool_lb_id = lb_ref.get("id", "")
                break
            if allowed_lb_ids is not None and pool_lb_id not in allowed_lb_ids:
                continue

            pool_id = pool["id"]
            allowed_pool_ids.add(pool_id)
            pool_name = pool.get("name", pool_id[:8])
            parent_lb_name = pool_lb_id[:8] if pool_lb_id else ""

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
        return allowed_pool_ids

    def _collect_healthmonitors(
        self, base: str, headers: dict, allowed_pool_ids: Optional[set]
    ) -> None:
        hm_data = api_get(f"{base}/v2.0/lbaas/healthmonitors", headers)
        for hm in hm_data.get("healthmonitors", []):
            hm_pools = hm.get("pools", [])
            hm_pool_id = hm_pools[0]["id"] if hm_pools else ""
            if allowed_pool_ids is not None and hm_pool_id not in allowed_pool_ids:
                continue
            hm_id = hm["id"]
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

    def _collect_listeners(
        self, base: str, headers: dict, allowed_lb_ids: Optional[set]
    ) -> None:
        listeners_data = api_get(f"{base}/v2.0/lbaas/listeners", headers)
        for li in listeners_data.get("listeners", []):
            parent_lb_id = ""
            for lb_ref in li.get("loadbalancers", []):
                parent_lb_id = lb_ref.get("id", "")
                break
            if allowed_lb_ids is not None and parent_lb_id not in allowed_lb_ids:
                continue
            li_id = li["id"]
            protocol = li.get("protocol", "")
            port = str(li.get("protocol_port", ""))
            parent = parent_lb_id[:8] if parent_lb_id else ""
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
