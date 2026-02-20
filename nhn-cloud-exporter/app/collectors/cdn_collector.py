"""
CDN Metrics Collector
"""
import logging
from typing import List
import httpx
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
from app.auth import NHNAuth
from app.config import get_settings

logger = logging.getLogger(__name__)


class CDNCollector:
    """CDN 메트릭 수집"""
    
    def __init__(self, auth: NHNAuth):
        self.auth = auth
        self.settings = get_settings()
        self.api_url = self.settings.nhn_cdn_api_url
    
    async def collect(self) -> List:
        """CDN 메트릭 수집"""
        if not self.settings.cdn_enabled:
            return []
        
        metrics = []
        
        try:
            appkey = self.auth.get_appkey(service="cdn")
            headers = await self.auth.get_auth_headers(use_iam=False, service="cdn")
            
            # CDN 서비스 목록 조회 (v2.0 API)
            url = f"{self.api_url}/v2.0/appKeys/{appkey}/services"
            
            async with httpx.AsyncClient(timeout=self.settings.http_timeout) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 404:
                    logger.warning(
                        "CDN 서비스를 찾을 수 없습니다 (404). CDN 미사용 시 정상입니다. "
                        "사용 중이라면 Appkey·CDN API URL을 확인하세요."
                    )
                    return []
                response.raise_for_status()
                data = response.json()
                
                services = data.get("services", [])
                
                # 필터링
                service_ids_filter = []
                if self.settings.cdn_service_ids:
                    service_ids_filter = [id.strip() for id in self.settings.cdn_service_ids.split(",")]
                
                # CDN 서비스 상태 메트릭
                cdn_status = GaugeMetricFamily(
                    "nhn_cdn_service_status",
                    "CDN service status (1=active, 0=inactive)",
                    labels=["service_id", "service_name", "domain"]
                )
                
                # CDN 통계 메트릭 (가능한 경우)
                # 실제 API 응답 형식에 맞게 수정 필요
                for service in services:
                    service_id = service.get("serviceId", "")
                    service_name = service.get("serviceName", "")
                    domain = service.get("domain", "")
                    status = service.get("status", "")
                    
                    # 필터링
                    if service_ids_filter and service_id not in service_ids_filter:
                        continue
                    
                    status_value = 1.0 if status == "ACTIVE" else 0.0
                    cdn_status.add_metric(
                        [service_id, service_name, domain],
                        status_value
                    )
                    
                    # CDN 통계 조회 (캐시 히트율, 대역폭 등)
                    # 실제 API 엔드포인트 확인 필요
                    # 예: stats_url = f"{self.api_url}/v2.0/appKeys/{appkey}/services/{service_id}/statistics"
                
                metrics.append(cdn_status)
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("CDN API 404 - CDN 미사용 시 정상입니다.")
            else:
                logger.error(f"CDN 메트릭 수집 실패: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"CDN 메트릭 수집 실패: {e}", exc_info=True)
        
        return metrics
