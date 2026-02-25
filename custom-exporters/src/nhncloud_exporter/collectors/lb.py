"""
Load Balancer collector.

Collects LB, Pool, Member, HealthMonitor, Listener metrics.
API: OpenStack LBaaS v2.0 compatible (NHN Cloud Network API).
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from nhncloud_exporter import config
from nhncloud_exporter.auth import get_lb_token, is_lb_oauth2
from nhncloud_exporter.utils import api_get
from nhncloud_exporter.metrics import (
    exporter_scrape_errors,
    lb_admin_up,
    lb_info,
    lb_provisioning,
    lb_stats_active_connections,
    lb_stats_bytes_in,
    lb_stats_bytes_out,
    lb_stats_request_errors,
    lb_stats_total_connections,
    lb_status,
    listener_cert_expire_days,
    listener_connection_limit,
    listener_info,
    member_admin_up,
    member_status,
    member_weight,
    pool_healthy_member_count,
    pool_info,
    pool_member_count,
    pool_status,
    pool_unhealthy_member_count,
    healthmonitor_delay,
    healthmonitor_max_retries,
    healthmonitor_status,
    healthmonitor_timeout,
)

logger = logging.getLogger("nhncloud-exporter")


def _lb_step_from_url(url: str) -> str:
    """실패한 요청 URL에서 단계 이름 추론."""
    u = (url or "").lower()
    if "/lbaas/loadbalancers" in u:
        return "loadbalancers"
    if "/lbaas/pools/" in u and "/members" in u:
        return "pool_members"
    if "/lbaas/pools" in u:
        return "pools"
    if "/lbaas/healthmonitors" in u:
        return "healthmonitors"
    if "/lbaas/listeners" in u:
        return "listeners"
    if "/stats" in u:
        return "loadbalancer_stats"
    return "unknown"


def _log_lb_error(step: str, url: str, e: Exception) -> None:
    """LB API 실패 시 원인 파악용 상세 로그."""
    req_url = getattr(getattr(e, "request", None), "url", None) or url
    step_label = _lb_step_from_url(str(req_url))

    if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
        status = e.response.status_code
        body = (e.response.text or "")[:400].replace("\n", " ")
        logger.warning(
            "LB API 실패 [단계=%s] HTTP %s url=%s",
            step_label,
            status,
            req_url,
        )
        logger.warning("LB API 응답 본문: %s", body or "(비어 있음)")
        if status == 401:
            body_lower = (e.response.text or "").lower()
            if "unauthorized tenant" in body_lower or "tenant" in body_lower:
                logger.warning(
                    "LB 401 진단: Unauthorized tenant – 토큰은 발급됐지만 해당 tenant(프로젝트)가 Network/LB API 접근 권한이 없거나, "
                    "NHN_TENANT_ID가 로드밸런서가 속한 프로젝트 ID가 아닙니다. 콘솔에서 (1) LB가 속한 프로젝트 (2) 해당 프로젝트의 프로젝트 ID (3) 그 프로젝트에 접근 가능한 계정의 API 비밀번호 로 NHN_TENANT_ID, NHN_USERNAME, NHN_PASSWORD 를 맞춰보세요."
                )
            else:
                logger.warning(
                    "LB 401 진단: 인증 실패. Network API는 Keystone 토큰만 지원합니다. "
                    "NHN_TENANT_ID, NHN_USERNAME, NHN_PASSWORD(API 전용 비밀번호) 설정 후 "
                    "NHN_LB_OAUTH2_KEY/SECRET 는 비우세요."
                )
        elif status == 403:
            logger.warning(
                "LB 403 진단: 권한 없음. 해당 계정/프로젝트에 Load Balancer API 접근 권한이 있는지 콘솔에서 확인하세요."
            )
        elif status == 404:
            logger.warning(
                "LB 404 진단: 경로 없음. NHN_NETWORK_ENDPOINT가 LB API 주소인지 확인하세요. "
                "예: https://kr1-api-network-infrastructure.nhncloudservice.com"
            )
        elif status >= 500:
            logger.warning(
                "LB %s 진단: 서버 오류. NHN 측 일시 장애일 수 있습니다.", status
            )
    elif isinstance(e, requests.exceptions.ConnectionError):
        logger.warning(
            "LB API 실패 [단계=%s] 연결 오류 url=%s – %s (NHN_NETWORK_ENDPOINT 도달 가능한지 확인)",
            step_label,
            req_url,
            e,
        )
    elif isinstance(e, requests.exceptions.Timeout):
        logger.warning(
            "LB API 실패 [단계=%s] 타임아웃 url=%s (네트워크 또는 엔드포인트 확인)",
            step_label,
            req_url,
        )
    elif isinstance(e, (ValueError, TypeError)):
        logger.warning(
            "LB API 실패 [단계=%s] 응답 파싱 오류 url=%s – %s (API가 JSON 대신 HTML 등 반환했을 수 있음, 인증/URL 확인)",
            step_label,
            req_url,
            e,
        )
    else:
        logger.warning(
            "LB API 실패 [단계=%s] url=%s – %s",
            step_label,
            req_url,
            e,
        )


def _clear_pool_member_series(pool_id: str, lb_name: str) -> None:
    """해당 풀에 속한 멤버 시리즈만 제거하여, 이번 스크래핑에서 running 멤버만 다시 남기기 위함."""
    for gauge in (member_status, member_admin_up, member_weight):
        # Gauge._metrics 키 순서: (pool_id, pool_name, member_id, member_address, member_port, lb_name)
        to_remove = [
            k for k in list(getattr(gauge, "_metrics", {}).keys())
            if len(k) >= 6 and k[0] == pool_id and k[5] == lb_name
        ]
        for k in to_remove:
            try:
                gauge.remove(*k)
            except KeyError:
                pass


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

        base = config.NHN_NETWORK_ENDPOINT.rstrip("/")
        try:
            token = get_lb_token()
        except Exception as e:
            logger.warning(
                "LB 토큰 발급 실패 – %s (Keystone: NHN_TENANT_ID, NHN_USERNAME, NHN_PASSWORD / OAuth2: NHN_LB_OAUTH2_KEY, NHN_LB_OAUTH2_SECRET 및 URL 확인)",
                e,
            )
            exporter_scrape_errors.labels(collector="loadbalancer").inc()
            return

        headers = {"X-Auth-Token": token}
        if is_lb_oauth2():
            headers["Authorization"] = f"Bearer {token}"
            logger.debug("LB auth: OAuth2 (Network API may 401; set NHN_TENANT_ID/USERNAME/PASSWORD to use Keystone)")
        else:
            if config.NHN_TENANT_ID:
                headers["X-Tenant-Id"] = config.NHN_TENANT_ID
            logger.debug("LB auth: Keystone")

        try:
            lb_data = api_get(f"{base}/v2.0/lbaas/loadbalancers", headers)
            lb_list = lb_data.get("loadbalancers", [])
            if not isinstance(lb_list, list):
                lb_list = []
            allowed_lb_ids = _allowed_lb_ids(lb_list)
            lb_id_to_name = {lb["id"]: lb.get("name", lb["id"][:8]) for lb in lb_list}

            self._collect_loadbalancers(lb_list, allowed_lb_ids)
            self._collect_loadbalancer_stats(base, headers, lb_list, allowed_lb_ids, lb_id_to_name)
            allowed_pool_ids = self._collect_pools_and_members(
                base, headers, lb_list, allowed_lb_ids, lb_id_to_name
            )
            self._collect_healthmonitors(base, headers, allowed_pool_ids)
            self._collect_listeners(base, headers, allowed_lb_ids, lb_id_to_name)
        except Exception as e:
            req_url = getattr(getattr(e, "request", None), "url", None) or ""
            _log_lb_error("collect", req_url or base or "", e)
            exporter_scrape_errors.labels(collector="loadbalancer").inc()

    def _collect_loadbalancers(self, lb_list: list, allowed_lb_ids: Optional[set]) -> None:
        for lb in lb_list:
            lb_id = lb["id"]
            if allowed_lb_ids is not None and lb_id not in allowed_lb_ids:
                continue
            lb_name = lb.get("name", lb_id[:8])
            lb_info.labels(lb_id=lb_id).info({
                "name": lb_name,
                "vip_address": lb.get("vip_address", ""),
                "provider": lb.get("provider", ""),
                "description": lb.get("description", "") or "",
            })
            lb_status.labels(lb_id=lb_id, lb_name=lb_name).set(
                1 if lb.get("operating_status", "").upper() == "ONLINE" else 0
            )
            lb_provisioning.labels(lb_id=lb_id, lb_name=lb_name).set(
                1 if lb.get("provisioning_status", "").upper() == "ACTIVE" else 0
            )
            lb_admin_up.labels(lb_id=lb_id, lb_name=lb_name).set(
                1 if lb.get("admin_state_up", False) else 0
            )

    def _collect_loadbalancer_stats(
        self,
        base: str,
        headers: dict,
        lb_list: list,
        allowed_lb_ids: Optional[set],
        lb_id_to_name: dict,
    ) -> None:
        """LB별 통계 수집 (Octavia 호환 GET /v2.0/lbaas/loadbalancers/{id}/stats). NHN 미지원 시 무시."""
        for lb in lb_list:
            lb_id = lb["id"]
            if allowed_lb_ids is not None and lb_id not in allowed_lb_ids:
                continue
            lb_name = lb_id_to_name.get(lb_id, lb_id[:8])
            try:
                data = api_get(f"{base}/v2.0/lbaas/loadbalancers/{lb_id}/stats", headers)
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    logger.debug("LB stats API not available for %s (404)", lb_id)
                else:
                    _log_lb_error("loadbalancer_stats", f"{base}/v2.0/lbaas/loadbalancers/{lb_id}/stats", e)
                continue
            except Exception as e:
                _log_lb_error("loadbalancer_stats", f"{base}/v2.0/lbaas/loadbalancers/{lb_id}/stats", e)
                continue
            labels = {"lb_id": lb_id, "lb_name": lb_name}
            raw = data if isinstance(data, dict) else {}
            stats = raw.get("stats", raw) if isinstance(raw.get("stats"), dict) else raw
            lb_stats_active_connections.labels(**labels).set(stats.get("active_connections", 0))
            lb_stats_total_connections.labels(**labels).set(stats.get("total_connections", 0))
            lb_stats_bytes_in.labels(**labels).set(stats.get("bytes_in", 0))
            lb_stats_bytes_out.labels(**labels).set(stats.get("bytes_out", 0))
            lb_stats_request_errors.labels(**labels).set(stats.get("request_errors", 0))

    def _collect_pools_and_members(
        self,
        base: str,
        headers: dict,
        lb_list: list,
        allowed_lb_ids: Optional[set],
        lb_id_to_name: dict,
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
            parent_lb_name = lb_id_to_name.get(pool_lb_id, pool_lb_id[:8] if pool_lb_id else "")

            pool_info.labels(
                pool_id=pool_id, pool_name=pool_name, lb_name=parent_lb_name
            ).info({
                "protocol": pool.get("protocol", ""),
                "lb_algorithm": pool.get("lb_algorithm", ""),
            })
            pool_status.labels(
                pool_id=pool_id, pool_name=pool_name, lb_name=parent_lb_name
            ).set(1 if pool.get("operating_status", "").upper() == "ONLINE" else 0)

            members_data = api_get(
                f"{base}/v2.0/lbaas/pools/{pool_id}/members", headers
            )
            members = members_data.get("members", [])
            total = len(members)
            # NHN Cloud는 정상 멤버에 operating_status "ACTIVE" 또는 "ONLINE" 반환
            def _member_healthy(m: dict) -> bool:
                status = (m.get("operating_status") or "").upper()
                return status in ("ONLINE", "ACTIVE")
            healthy = sum(1 for m in members if _member_healthy(m))
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

            # 현재 실행 중인 멤버만 멤버 단위 메트릭으로 노출 (추이: 스크래핑마다 갱신되어 리스트가 바뀜)
            def _member_running(m: dict) -> bool:
                return _member_healthy(m) and bool(m.get("admin_state_up", False))

            # 이 풀에 대한 기존 멤버 시리즈 제거 → 이번 스크래핑에서 running 만 다시 설정
            _clear_pool_member_series(pool_id, parent_lb_name)

            for m in members:
                if not _member_running(m):
                    continue
                labels = {
                    "pool_id": pool_id,
                    "pool_name": pool_name,
                    "member_id": m["id"],
                    "member_address": m.get("address", ""),
                    "member_port": str(m.get("protocol_port", "")),
                    "lb_name": parent_lb_name,
                }
                member_status.labels(**labels).set(1)
                member_admin_up.labels(**labels).set(1)
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
        self,
        base: str,
        headers: dict,
        allowed_lb_ids: Optional[set],
        lb_id_to_name: dict,
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
            parent = lb_id_to_name.get(parent_lb_id, parent_lb_id[:8] if parent_lb_id else "")
            listener_info.labels(listener_id=li_id, lb_name=parent).info({
                "protocol": protocol,
                "port": port,
                "default_pool_id": li.get("default_pool_id", "") or "",
            })
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
