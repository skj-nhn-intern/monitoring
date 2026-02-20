"""
Configuration for NHN Cloud Exporter.
"""
import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# .env 파일 로드 (프로젝트 루트에서 찾기)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # 현재 디렉토리에서도 시도
    load_dotenv()


class Environment(str, Enum):
    """Application environment modes."""
    DEV = "DEV"
    PRODUCTION = "PRODUCTION"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Environment
    environment: Environment = Field(
        default=Environment.DEV,
        description="Application environment: DEV or PRODUCTION"
    )
    
    # Application
    app_name: str = Field(default="NHN Cloud Exporter")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)
    
    # NHN Cloud API Authentication
    # 서비스별 Appkey (각 서비스마다 다른 Appkey가 필요할 수 있음)
    nhn_dnsplus_appkey: str = Field(default="", description="DNS Plus Appkey (GSLB용)")
    nhn_cdn_appkey: str = Field(default="", description="CDN Appkey (CDN용)")
    nhn_rds_appkey: str = Field(default="", description="RDS Appkey (RDS API v3용, X-TC-APP-KEY 헤더)")
    # 하위 호환성을 위한 기본 Appkey (설정되지 않은 경우 DNS Plus/CDN/RDS Appkey로 폴백)
    nhn_appkey: str = Field(default="", description="NHN Cloud Appkey (하위 호환성, 서비스별 Appkey 미지정 시 사용)")
    
    # IAM 인증 (Load Balancer, RDS 등)
    nhn_iam_user: str = Field(default="", description="IAM 사용자명")
    nhn_iam_password: str = Field(default="", description="IAM 비밀번호")
    nhn_tenant_id: str = Field(default="", description="Tenant ID")
    nhn_auth_url: str = Field(
        default="https://api-identity-infrastructure.nhncloudservice.com/v2.0",
        description="IAM 인증 URL"
    )
    
    # API Endpoints
    nhn_dnsplus_api_url: str = Field(
        default="https://dnsplus.api.nhncloudservice.com",
        description="DNS Plus API URL"
    )
    nhn_lb_api_url: str = Field(
        default="https://kr1-api-network-infrastructure.nhncloudservice.com",
        description="Load Balancer API URL"
    )
    nhn_rds_api_url: str = Field(
        default="https://kr1-rds-mysql.api.nhncloudservice.com",
        description="RDS API URL (e.g. kr1-rds-mysql.api.nhncloudservice.com)"
    )
    # RDS API v3 uses X-TC-* headers (not IAM token)
    nhn_access_key_id: str = Field(default="", description="API User Access Key ID (RDS API)")
    nhn_access_key_secret: str = Field(default="", description="API Secret Access Key (RDS API)")
    nhn_cdn_api_url: str = Field(
        default="https://cdn.api.nhncloudservice.com",
        description="CDN API URL"
    )
    nhn_obs_api_url: str = Field(
        default="https://kr1-api-object-storage.nhncloudservice.com",
        description="Object Storage API URL"
    )
    nhn_compute_api_url: str = Field(
        default="https://kr1-api-compute.infrastructure.nhncloudservice.com",
        description="Compute API URL (Instance metrics)"
    )
    
    # Monitoring Configuration
    metrics_collection_interval: int = Field(
        default=60,
        description="메트릭 수집 주기 (초)"
    )
    metrics_cache_ttl: int = Field(
        default=30,
        description="메트릭 캐시 TTL (초)"
    )
    http_timeout: float = Field(
        default=30.0,
        description="HTTP 요청 타임아웃 (초)"
    )
    
    # Service-specific settings
    # GSLB
    gslb_enabled: bool = Field(default=True, description="GSLB 메트릭 수집 활성화")
    
    # Load Balancer
    lb_enabled: bool = Field(default=True, description="Load Balancer 메트릭 수집 활성화")
    lb_ids: str = Field(default="", description="모니터링할 Load Balancer ID 목록 (쉼표 구분)")
    
    # RDS
    rds_enabled: bool = Field(default=True, description="RDS 메트릭 수집 활성화")
    rds_instance_ids: str = Field(default="", description="모니터링할 RDS 인스턴스 ID 목록 (쉼표 구분)")
    
    # CDN
    cdn_enabled: bool = Field(default=True, description="CDN 메트릭 수집 활성화")
    cdn_service_ids: str = Field(default="", description="모니터링할 CDN 서비스 ID 목록 (쉼표 구분)")
    
    # OBS
    obs_enabled: bool = Field(default=True, description="Object Storage 메트릭 수집 활성화")
    obs_containers: str = Field(default="", description="모니터링할 컨테이너 목록 (쉼표 구분)")
    # Object Storage 전용 API 비밀번호 (콘솔 Object Storage > API Endpoint 설정 > Set API Password)
    # 설정 시 OBS 요청만 이 비밀번호로 토큰 발급. 비우면 NHN_IAM_PASSWORD 사용.
    nhn_obs_api_password: str = Field(default="", description="OBS API 비밀번호 (Set API Password 값)")
    
    # Instance Metrics (Cloud Monitoring API)
    instance_enabled: bool = Field(default=True, description="인스턴스 메트릭 수집 활성화")
    instance_ids: str = Field(default="", description="모니터링할 인스턴스 ID 목록 (쉼표 구분)")
    
    # Service Operations Metrics (서비스 운영 지표)
    service_operations_enabled: bool = Field(
        default=True,
        description="서비스 운영 지표 수집 활성화 (CDN 캐시 효율성, OBS 사용량, RDS 성능 등)"
    )
    
    # Photo API Service Configuration
    photo_api_obs_container: str = Field(
        default="photo-container",
        description="Photo API Object Storage 컨테이너 이름"
    )
    photo_api_cdn_app_key: str = Field(
        default="",
        description="Photo API CDN App Key (CDN 서비스 식별용, CDN 콘솔에서 확인)"
    )
    photo_api_rds_instance_id: str = Field(
        default="",
        description="Photo API RDS 인스턴스 ID"
    )
    photo_api_lb_ids: str = Field(
        default="",
        description="Photo API Load Balancer ID 목록 (쉼표 구분, 트래픽 분산 효율성 모니터링)"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
