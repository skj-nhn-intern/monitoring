"""
NHN Cloud API Authentication
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)


class NHNAuth:
    """NHN Cloud API 인증 관리"""
    
    def __init__(self):
        self.settings = get_settings()
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._obs_storage_url: Optional[str] = None  # from token serviceCatalog
        self._lb_api_url: Optional[str] = None  # from token serviceCatalog (network service)
        # OBS 전용 토큰 (NHN_OBS_API_PASSWORD 사용 시)
        self._token_obs: Optional[str] = None
        self._token_obs_expires: Optional[datetime] = None
        self._obs_storage_url_obs: Optional[str] = None
    
    async def get_iam_token(self, use_obs_password: bool = False) -> str:
        """
        IAM 토큰 획득 (캐싱 및 자동 갱신).
        use_obs_password=True 이고 NHN_OBS_API_PASSWORD가 설정되어 있으면,
        OBS 전용 API 비밀번호로 토큰 발급(캐시는 별도).
        """
        use_obs_pw = use_obs_password and bool(self.settings.nhn_obs_api_password and self.settings.nhn_obs_api_password.strip())
        if use_obs_password and not use_obs_pw:
            logger.warning(
                "OBS 토큰: NHN_OBS_API_PASSWORD가 비어 있음. IAM 비밀번호로 발급 중이며 403 나올 수 있음. "
                ".env에 NHN_OBS_API_PASSWORD=콘솔_Set_API_Password_값 을 넣고 컨테이너 재시작하세요."
            )
        password = self.settings.nhn_obs_api_password.strip() if use_obs_pw else self.settings.nhn_iam_password
        cache_obs = use_obs_pw
        
        now_utc = datetime.now(timezone.utc)
        if cache_obs:
            if (
                self._token_obs
                and self._token_obs_expires
                and now_utc < self._token_obs_expires - timedelta(minutes=5)
            ):
                if self._obs_storage_url_obs is not None:
                    self._obs_storage_url = self._obs_storage_url_obs
                return self._token_obs
        else:
            if (
                self._token
                and self._token_expires
                and now_utc < self._token_expires - timedelta(minutes=5)
            ):
                return self._token
        
        if not self.settings.nhn_iam_user or not password:
            raise ValueError(
                "IAM 인증 정보가 설정되지 않았습니다."
                + (" OBS 사용 시 NHN_OBS_API_PASSWORD 또는 NHN_IAM_PASSWORD를 설정하세요." if use_obs_password else "")
            )
        
        auth_url = f"{self.settings.nhn_auth_url}/tokens"
        auth_data = {
            "auth": {
                "tenantId": self.settings.nhn_tenant_id,
                "passwordCredentials": {
                    "username": self.settings.nhn_iam_user,
                    "password": password
                }
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.settings.http_timeout) as client:
                response = await client.post(
                    auth_url,
                    json=auth_data,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                data = response.json()
                
                access = data.get("access", {})
                token_data = access.get("token", {})
                token_id = token_data.get("id")
                expires_str = token_data.get("expires")
                
                if not token_id or not expires_str:
                    raise ValueError("토큰 응답 형식이 올바르지 않습니다.")
                
                expires_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                storage_url = self._parse_obs_storage_url(access)
                lb_url = self._parse_lb_api_url(access)
                
                # 디버깅: service catalog 로깅 (DEBUG 모드에서만)
                if self.settings.debug:
                    catalog = access.get("serviceCatalog", [])
                    service_types = [svc.get("type", "unknown") for svc in catalog]
                    logger.debug(f"Service Catalog 타입 목록: {', '.join(service_types)}")
                
                if cache_obs:
                    self._token_obs = token_id
                    self._token_obs_expires = expires_dt
                    self._obs_storage_url_obs = storage_url
                    self._obs_storage_url = storage_url
                    logger.info("IAM 토큰 발급 완료 (OBS API 비밀번호 사용)")
                else:
                    self._token = token_id
                    self._token_expires = expires_dt
                    self._obs_storage_url = storage_url
                    self._lb_api_url = lb_url
                    if lb_url:
                        logger.info(f"IAM 토큰 발급 완료 (Load Balancer API URL: {lb_url})")
                    else:
                        logger.warning("IAM 토큰 발급 완료 (Load Balancer API URL: service catalog에서 찾을 수 없음, 설정값 사용). DEBUG=true로 설정하면 service catalog를 확인할 수 있습니다.")
                
                return token_id
        except httpx.HTTPStatusError as e:
            logger.error(f"IAM 토큰 발급 실패: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"IAM 토큰 발급 중 오류: {e}")
            raise
    
    def _parse_obs_storage_url(self, access: dict) -> Optional[str]:
        """토큰 응답의 serviceCatalog에서 object-store publicURL 추출"""
        try:
            catalog = access.get("serviceCatalog", [])
            for svc in catalog:
                if svc.get("type") == "object-store":
                    endpoints = svc.get("endpoints", [])
                    if endpoints:
                        return endpoints[0].get("publicURL") or endpoints[0].get("internalURL")
            return None
        except Exception:
            return None
    
    def _parse_lb_api_url(self, access: dict) -> Optional[str]:
        """토큰 응답의 serviceCatalog에서 network 서비스 publicURL 추출 (Load Balancer용)"""
        try:
            catalog = access.get("serviceCatalog", [])
            for svc in catalog:
                # network 서비스 타입 확인
                service_type = svc.get("type", "")
                service_name = svc.get("name", "")
                # network 또는 load-balancer 관련 서비스 찾기
                if "network" in service_type.lower() or "loadbalancer" in service_type.lower() or "lbaas" in service_type.lower():
                    endpoints = svc.get("endpoints", [])
                    if endpoints:
                        url = endpoints[0].get("publicURL") or endpoints[0].get("internalURL")
                        if url:
                            return url.rstrip("/")
                # 또는 service name으로 확인
                elif "network" in service_name.lower() or "loadbalancer" in service_name.lower():
                    endpoints = svc.get("endpoints", [])
                    if endpoints:
                        url = endpoints[0].get("publicURL") or endpoints[0].get("internalURL")
                        if url:
                            return url.rstrip("/")
            return None
        except Exception as e:
            logger.debug(f"Load Balancer API URL 파싱 실패: {e}")
            return None
    
    def get_lb_api_url(self) -> Optional[str]:
        """Load Balancer API URL (토큰 카탈로그 또는 설정 기반). LB 수집 전 get_iam_token 호출 필요."""
        return self._lb_api_url
    
    def get_obs_storage_url(self) -> Optional[str]:
        """Object Storage base URL (토큰 카탈로그 또는 설정 기반). OBS 수집 전 get_iam_token 호출 필요."""
        return self._obs_storage_url
    
    def get_rds_auth_headers(self) -> Optional[dict]:
        """
        RDS API v3 인증 헤더 (X-TC-APP-KEY, X-TC-AUTHENTICATION-*).
        설정되어 있으면 반환, 없으면 None (IAM 사용).
        """
        # RDS Appkey 우선, 없으면 기본 Appkey 사용
        rds_appkey = self.settings.nhn_rds_appkey or self.settings.nhn_appkey
        if not rds_appkey or not self.settings.nhn_access_key_id or not self.settings.nhn_access_key_secret:
            return None
        return {
            "X-TC-APP-KEY": rds_appkey,
            "X-TC-AUTHENTICATION-ID": self.settings.nhn_access_key_id,
            "X-TC-AUTHENTICATION-SECRET": self.settings.nhn_access_key_secret,
            "Content-Type": "application/json",
        }
    
    def get_appkey(self, service: str = "default") -> str:
        """
        서비스별 Appkey 반환
        service: "dnsplus", "cdn", "rds", "default"
        """
        if service == "dnsplus":
            appkey = self.settings.nhn_dnsplus_appkey or self.settings.nhn_appkey
        elif service == "cdn":
            appkey = self.settings.nhn_cdn_appkey or self.settings.nhn_appkey
        elif service == "rds":
            appkey = self.settings.nhn_rds_appkey or self.settings.nhn_appkey
        else:
            appkey = self.settings.nhn_appkey
        
        if not appkey:
            raise ValueError(f"{service} Appkey가 설정되지 않았습니다. NHN_{service.upper()}_APPKEY 또는 NHN_APPKEY를 설정하세요.")
        return appkey
    
    async def get_auth_headers(self, use_iam: bool = True, use_obs_password: bool = False, service: str = "default") -> dict:
        """
        인증 헤더 반환
        use_iam=True: IAM 토큰 사용 (Load Balancer, OBS 등)
        use_obs_password=True: OBS 전용 API 비밀번호로 토큰 발급 (NHN_OBS_API_PASSWORD 설정 시)
        use_iam=False: Appkey 사용 (DNS Plus, CDN 등)
        service: "dnsplus", "cdn", "rds", "default" (use_iam=False일 때만 사용)
        """
        if use_iam:
            token = await self.get_iam_token(use_obs_password=use_obs_password)
            headers = {
                "X-Auth-Token": token,
                "Content-Type": "application/json"
            }
            # Load Balancer API 등 일부 서비스에서 필요할 수 있는 헤더 추가
            # OpenStack 스타일 API에서는 X-Auth-Project-Id 또는 X-Tenant-Id가 필요할 수 있음
            if self.settings.nhn_tenant_id:
                headers["X-Auth-Project-Id"] = self.settings.nhn_tenant_id
            return headers
        else:
            return {
                "X-TC-APP-KEY": self.get_appkey(service=service),
                "Content-Type": "application/json"
            }
