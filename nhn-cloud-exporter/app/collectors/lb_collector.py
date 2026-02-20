"""
Load Balancer Metrics Collector
"""
import logging
from typing import List
import httpx
from prometheus_client.core import GaugeMetricFamily
from app.auth import NHNAuth
from app.config import get_settings

logger = logging.getLogger(__name__)


class LoadBalancerCollector:
    """Load Balancer 메트릭 수집"""
    
    def __init__(self, auth: NHNAuth):
        self.auth = auth
        self.settings = get_settings()
        self.api_url = self.settings.nhn_lb_api_url
    
    async def collect(self) -> List:
        """Load Balancer 메트릭 수집"""
        if not self.settings.lb_enabled:
            return []
        
        metrics = []
        
        try:
            headers = await self.auth.get_auth_headers(use_iam=True)
            
            # Load Balancer 목록 조회
            url = f"{self.api_url}/v2.0/lbaas/loadbalancers"
            
            async with httpx.AsyncClient(timeout=self.settings.http_timeout) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 401:
                    # 토큰 만료 가능성 - 토큰 갱신 후 재시도
                    logger.warning("Load Balancer API 401 - 토큰 갱신 후 재시도합니다.")
                    # 토큰 캐시 무효화를 위해 새로운 토큰 요청
                    self.auth._token = None
                    self.auth._token_expires = None
                    headers = await self.auth.get_auth_headers(use_iam=True)
                    response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                loadbalancers = data.get("loadbalancers", [])
                
                # 필터링 (설정된 ID 목록이 있으면)
                lb_ids_filter = []
                if self.settings.lb_ids:
                    lb_ids_filter = [id.strip() for id in self.settings.lb_ids.split(",")]
                
                # Load Balancer 상태 메트릭
                lb_operating_status = GaugeMetricFamily(
                    "nhn_lb_operating_status",
                    "Load Balancer operating status (1=ONLINE, 0=OFFLINE)",
                    labels=["lb_id", "lb_name", "vip_address"]
                )
                
                lb_provisioning_status = GaugeMetricFamily(
                    "nhn_lb_provisioning_status",
                    "Load Balancer provisioning status (1=ACTIVE, 0=other)",
                    labels=["lb_id", "lb_name", "status"]
                )
                
                # Listener 상태 메트릭
                listener_status = GaugeMetricFamily(
                    "nhn_lb_listener_status",
                    "Load Balancer Listener operating status (1=ONLINE, 0=OFFLINE)",
                    labels=["lb_id", "listener_id", "listener_name", "protocol", "port"]
                )
                
                # Pool 상태 메트릭
                pool_status = GaugeMetricFamily(
                    "nhn_lb_pool_status",
                    "Load Balancer Pool operating status (1=ONLINE, 0=OFFLINE)",
                    labels=["lb_id", "pool_id", "pool_name", "protocol"]
                )
                
                # Pool Member 상태 메트릭
                member_status = GaugeMetricFamily(
                    "nhn_lb_pool_member_status",
                    "Load Balancer Pool Member monitor status (1=ONLINE, 0=OFFLINE)",
                    labels=["lb_id", "pool_id", "member_id", "member_address", "member_port"]
                )
                
                for lb in loadbalancers:
                    lb_id = lb.get("id", "")
                    lb_name = lb.get("name", "")
                    
                    # 필터링
                    if lb_ids_filter and lb_id not in lb_ids_filter:
                        continue
                    
                    # Operating Status
                    operating_status = lb.get("operating_status", "")
                    operating_value = 1.0 if operating_status == "ONLINE" else 0.0
                    vip_address = lb.get("vip_address", "")
                    lb_operating_status.add_metric(
                        [lb_id, lb_name, vip_address],
                        operating_value
                    )
                    
                    # Provisioning Status
                    provisioning_status = lb.get("provisioning_status", "")
                    provisioning_value = 1.0 if provisioning_status == "ACTIVE" else 0.0
                    lb_provisioning_status.add_metric(
                        [lb_id, lb_name, provisioning_status],
                        provisioning_value
                    )
                    
                    # Listener 조회
                    listeners_url = f"{self.api_url}/v2.0/lbaas/listeners?loadbalancer_id={lb_id}"
                    try:
                        listeners_response = await client.get(listeners_url, headers=headers)
                        listeners_response.raise_for_status()
                        listeners_data = listeners_response.json()
                        listeners = listeners_data.get("listeners", [])
                        
                        for listener in listeners:
                            listener_id = listener.get("id", "")
                            listener_name = listener.get("name", "")
                            listener_protocol = listener.get("protocol", "")
                            listener_port = str(listener.get("protocol_port", ""))
                            listener_operating_status = listener.get("operating_status", "")
                            
                            listener_status_value = 1.0 if listener_operating_status == "ONLINE" else 0.0
                            listener_status.add_metric(
                                [lb_id, listener_id, listener_name, listener_protocol, listener_port],
                                listener_status_value
                            )
                    except Exception as e:
                        logger.warning(f"Listener 조회 실패 (LB {lb_id}): {e}")
                    
                    # Pool 조회
                    pools_url = f"{self.api_url}/v2.0/lbaas/pools?loadbalancer_id={lb_id}"
                    try:
                        pools_response = await client.get(pools_url, headers=headers)
                        pools_response.raise_for_status()
                        pools_data = pools_response.json()
                        pools = pools_data.get("pools", [])
                        
                        for pool in pools:
                            pool_id = pool.get("id", "")
                            pool_name = pool.get("name", "")
                            pool_protocol = pool.get("protocol", "")
                            pool_operating_status = pool.get("operating_status", "")
                            
                            pool_status_value = 1.0 if pool_operating_status == "ONLINE" else 0.0
                            pool_status.add_metric(
                                [lb_id, pool_id, pool_name, pool_protocol],
                                pool_status_value
                            )
                            
                            # Pool Member 조회
                            members_url = f"{self.api_url}/v2.0/lbaas/pools/{pool_id}/members"
                            try:
                                members_response = await client.get(members_url, headers=headers)
                                members_response.raise_for_status()
                                members_data = members_response.json()
                                members = members_data.get("members", [])
                                
                                for member in members:
                                    member_id = member.get("id", "")
                                    member_address = member.get("address", "")
                                    member_port = str(member.get("protocol_port", ""))
                                    monitor_status = member.get("monitor_status", "")
                                    
                                    member_status_value = 1.0 if monitor_status == "ONLINE" else 0.0
                                    member_status.add_metric(
                                        [lb_id, pool_id, member_id, member_address, member_port],
                                        member_status_value
                                    )
                            except Exception as e:
                                logger.warning(f"Pool Member 조회 실패 (Pool {pool_id}): {e}")
                    except Exception as e:
                        logger.warning(f"Pool 조회 실패 (LB {lb_id}): {e}")
                
                metrics.extend([
                    lb_operating_status,
                    lb_provisioning_status,
                    listener_status,
                    pool_status,
                    member_status
                ])
                
        except Exception as e:
            logger.error(f"Load Balancer 메트릭 수집 실패: {e}", exc_info=True)
        
        return metrics
