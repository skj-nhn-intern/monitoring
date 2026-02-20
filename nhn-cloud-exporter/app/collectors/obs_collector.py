"""
Object Storage Metrics Collector
"""
import logging
from typing import List
import httpx
from prometheus_client.core import GaugeMetricFamily
from app.auth import NHNAuth
from app.config import get_settings

logger = logging.getLogger(__name__)


class OBSCollector:
    """Object Storage 메트릭 수집"""
    
    def __init__(self, auth: NHNAuth):
        self.auth = auth
        self.settings = get_settings()
        self.api_url = self.settings.nhn_obs_api_url
    
    async def collect(self) -> List:
        """Object Storage 메트릭 수집"""
        if not self.settings.obs_enabled:
            return []
        
        metrics = []
        
        try:
            # OBS 전용 API 비밀번호(NHN_OBS_API_PASSWORD)가 있으면 그걸로 토큰 발급
            token = await self.auth.get_iam_token(use_obs_password=True)
            headers = {"X-Auth-Token": token, "Accept": "application/json"}
            
            # 스토리지 URL: 토큰 카탈로그 우선, 없으면 설정 기반
            base_url = self.auth.get_obs_storage_url()
            if base_url:
                # publicURL 형식: https://.../v1/AUTH_xxx (끝에 슬래시 없음)
                base_url = base_url.rstrip("/")
                containers_url = base_url
                account = base_url.split("/")[-1] if "/" in base_url else "default"
            else:
                tenant_id = self.settings.nhn_tenant_id
                account = f"AUTH_{tenant_id}"
                containers_url = f"{self.api_url}/v1/{account}"
            
            async with httpx.AsyncClient(timeout=self.settings.http_timeout) as client:
                response = await client.get(
                    containers_url,
                    headers=headers
                )
                if response.status_code == 403:
                    logger.warning(
                        "Object Storage 접근 거부 (403). API Endpoint 비밀번호·프로젝트 권한을 확인하세요."
                    )
                    return []
                response.raise_for_status()
                # 컨테이너 목록 파싱 (빈 줄, 공백, 특수 문자 제거)
                containers_raw = response.text.strip().split("\n") if response.text else []
                containers = [c.strip() for c in containers_raw if c.strip() and not c.strip().startswith("[") and not c.strip().endswith("]")]
                
                # 필터링
                containers_filter = []
                if self.settings.obs_containers:
                    containers_filter = [c.strip() for c in self.settings.obs_containers.split(",") if c.strip()]
                
                # 컨테이너별 스토리지 사용량
                container_storage = GaugeMetricFamily(
                    "nhn_obs_container_storage_bytes",
                    "Object Storage container storage usage in bytes",
                    labels=["container_name", "account"]
                )
                
                container_object_count = GaugeMetricFamily(
                    "nhn_obs_container_object_count",
                    "Object Storage container object count",
                    labels=["container_name", "account"]
                )
                
                for container_name in containers:
                    if not container_name or container_name in ["[]", "{}", ""]:
                        continue
                    
                    # 필터링
                    if containers_filter and container_name not in containers_filter:
                        continue
                    
                    # 컨테이너 정보 조회
                    if base_url:
                        container_info_url = f"{base_url}/{container_name}"
                    else:
                        container_info_url = f"{self.api_url}/v1/{account}/{container_name}"
                    try:
                        info_response = await client.head(
                            container_info_url,
                            headers={"X-Auth-Token": token}
                        )
                        info_response.raise_for_status()
                        
                        # 헤더에서 정보 추출
                        bytes_used = int(info_response.headers.get("X-Container-Bytes-Used", 0))
                        object_count = int(info_response.headers.get("X-Container-Object-Count", 0))
                        
                        container_storage.add_metric(
                            [container_name, account],
                            float(bytes_used)
                        )
                        container_object_count.add_metric(
                            [container_name, account],
                            float(object_count)
                        )
                    except Exception as e:
                        logger.warning(f"컨테이너 정보 조회 실패 ({container_name}): {e}")
                
                metrics.extend([container_storage, container_object_count])
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.warning("Object Storage 403 - API 비밀번호·권한을 확인하세요.")
            elif e.response.status_code == 404:
                logger.warning("Object Storage 404 - 계정/URL을 확인하세요.")
            else:
                logger.error(f"Object Storage 메트릭 수집 실패: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Object Storage 메트릭 수집 실패: {e}", exc_info=True)
        
        return metrics
