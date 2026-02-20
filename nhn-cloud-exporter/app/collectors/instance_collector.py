"""
Instance Metrics Collector (Cloud Monitoring API)
"""
import logging
from typing import List
import httpx
from prometheus_client.core import GaugeMetricFamily
from app.auth import NHNAuth
from app.config import get_settings

logger = logging.getLogger(__name__)


class InstanceCollector:
    """인스턴스 메트릭 수집 (Cloud Monitoring API)"""
    
    def __init__(self, auth: NHNAuth):
        self.auth = auth
        self.settings = get_settings()
        self.api_url = self.settings.nhn_compute_api_url
    
    async def collect(self) -> List:
        """인스턴스 메트릭 수집"""
        if not self.settings.instance_enabled:
            return []
        
        metrics = []
        
        try:
            headers = await self.auth.get_auth_headers(use_iam=True)
            
            # 인스턴스 목록 조회
            url = f"{self.api_url}/v2.0/servers"
            
            async with httpx.AsyncClient(timeout=self.settings.http_timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                servers = data.get("servers", [])
                
                # 필터링
                instance_ids_filter = []
                if self.settings.instance_ids:
                    instance_ids_filter = [id.strip() for id in self.settings.instance_ids.split(",")]
                
                # 인스턴스 상태 메트릭
                instance_status = GaugeMetricFamily(
                    "nhn_instance_status",
                    "Instance status (1=ACTIVE, 0=other)",
                    labels=["instance_id", "instance_name", "status", "flavor_id"]
                )
                
                for server in servers:
                    instance_id = server.get("id", "")
                    instance_name = server.get("name", "")
                    status = server.get("status", "")
                    flavor_id = server.get("flavor", {}).get("id", "")
                    
                    # 필터링
                    if instance_ids_filter and instance_id not in instance_ids_filter:
                        continue
                    
                    status_value = 1.0 if status == "ACTIVE" else 0.0
                    instance_status.add_metric(
                        [instance_id, instance_name, status, flavor_id],
                        status_value
                    )
                
                metrics.append(instance_status)
                
                # 인스턴스 메트릭은 Cloud Monitoring API를 통해 별도로 조회 필요
                # 여기서는 기본 상태만 수집
                
        except httpx.ConnectError as e:
            logger.warning(f"인스턴스 API 연결 실패 (DNS 또는 네트워크 문제): {e}. Compute API URL을 확인하세요: {self.api_url}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.warning("인스턴스 API 401 - IAM 인증 정보를 확인하세요.")
            else:
                logger.error(f"인스턴스 API 오류: {e.response.status_code}")
        except Exception as e:
            logger.error(f"인스턴스 메트릭 수집 실패: {e}", exc_info=True)
        
        return metrics
