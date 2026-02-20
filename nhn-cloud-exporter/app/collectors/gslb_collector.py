"""
GSLB (DNS Plus) Metrics Collector
"""
import logging
from typing import Dict, List, Optional
import httpx
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
from app.auth import NHNAuth
from app.config import get_settings

logger = logging.getLogger(__name__)


class GSLBCollector:
    """GSLB 메트릭 수집"""
    
    def __init__(self, auth: NHNAuth):
        self.auth = auth
        self.settings = get_settings()
        self.api_url = self.settings.nhn_dnsplus_api_url
    
    async def collect(self) -> List:
        """GSLB 메트릭 수집"""
        if not self.settings.gslb_enabled:
            return []
        
        metrics = []
        
        try:
            appkey = self.auth.get_appkey(service="dnsplus")
            headers = await self.auth.get_auth_headers(use_iam=False, service="dnsplus")
            
            # GSLB 목록 조회
            url = f"{self.api_url}/dnsplus/v1.0/appkeys/{appkey}/gslbs"
            
            async with httpx.AsyncClient(timeout=self.settings.http_timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                gslbs = data.get("gslbs", [])
                
                # GSLB 상태 메트릭
                gslb_status = GaugeMetricFamily(
                    "nhn_gslb_status",
                    "GSLB operating status (1=ONLINE, 0=OFFLINE)",
                    labels=["gslb_id", "gslb_name"]
                )
                
                # Pool 상태 메트릭
                pool_status = GaugeMetricFamily(
                    "nhn_gslb_pool_status",
                    "GSLB Pool operating status (1=ONLINE, 0=OFFLINE)",
                    labels=["gslb_id", "pool_id", "pool_name"]
                )
                
                # Pool Member 상태 메트릭
                member_status = GaugeMetricFamily(
                    "nhn_gslb_pool_member_status",
                    "GSLB Pool Member operating status (1=ONLINE, 0=OFFLINE)",
                    labels=["gslb_id", "pool_id", "member_id", "member_name"]
                )
                
                # Health Check 상태 메트릭
                health_check_status = GaugeMetricFamily(
                    "nhn_gslb_health_check_status",
                    "GSLB Health Check status (1=healthy, 0=unhealthy)",
                    labels=["gslb_id", "health_check_id", "health_check_name"]
                )
                
                for gslb in gslbs:
                    gslb_id = gslb.get("gslbId", "")
                    gslb_name = gslb.get("gslbName", "")
                    operating_status = gslb.get("operatingStatus", "")
                    
                    # GSLB 상태 (ONLINE=1, OFFLINE=0)
                    status_value = 1.0 if operating_status == "ONLINE" else 0.0
                    gslb_status.add_metric([gslb_id, gslb_name], status_value)
                    
                    # Pool 조회
                    pools_url = f"{self.api_url}/dnsplus/v1.0/appkeys/{appkey}/gslbs/{gslb_id}/pools"
                    try:
                        pools_response = await client.get(pools_url, headers=headers)
                        pools_response.raise_for_status()
                        pools_data = pools_response.json()
                        pools = pools_data.get("pools", [])
                        
                        for pool in pools:
                            pool_id = pool.get("poolId", "")
                            pool_name = pool.get("poolName", "")
                            pool_operating_status = pool.get("operatingStatus", "")
                            
                            pool_status_value = 1.0 if pool_operating_status == "ONLINE" else 0.0
                            pool_status.add_metric(
                                [gslb_id, pool_id, pool_name],
                                pool_status_value
                            )
                            
                            # Pool Member 조회
                            members = pool.get("members", [])
                            for member in members:
                                member_id = member.get("memberId", "")
                                member_name = member.get("memberName", "")
                                member_operating_status = member.get("operatingStatus", "")
                                
                                member_status_value = 1.0 if member_operating_status == "ONLINE" else 0.0
                                member_status.add_metric(
                                    [gslb_id, pool_id, member_id, member_name],
                                    member_status_value
                                )
                    except Exception as e:
                        logger.warning(f"Pool 조회 실패 (GSLB {gslb_id}): {e}")
                
                # Health Check 조회
                health_checks_url = f"{self.api_url}/dnsplus/v1.0/appkeys/{appkey}/health-checks"
                try:
                    hc_response = await client.get(health_checks_url, headers=headers)
                    hc_response.raise_for_status()
                    hc_data = hc_response.json()
                    health_checks = hc_data.get("healthChecks", [])
                    
                    for hc in health_checks:
                        hc_id = hc.get("healthCheckId", "")
                        hc_name = hc.get("healthCheckName", "")
                        # Health Check 상태는 Pool 연결 정보에서 확인 필요
                        # 여기서는 기본값으로 설정
                        health_check_status.add_metric(
                            [gslb_id, hc_id, hc_name],
                            1.0
                        )
                except Exception as e:
                    logger.warning(f"Health Check 조회 실패: {e}")
                
                metrics.extend([gslb_status, pool_status, member_status, health_check_status])
                
        except Exception as e:
            logger.error(f"GSLB 메트릭 수집 실패: {e}", exc_info=True)
        
        return metrics
