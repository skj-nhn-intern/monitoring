"""
NHN Cloud Infrastructure Metrics Exporter
FastAPI application that exposes Prometheus metrics for NHN Cloud services
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.core import CollectorRegistry
from starlette.responses import Response

# .env 파일 로드 (프로젝트 루트에서 찾기)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # 현재 디렉토리에서도 시도
    load_dotenv()

from app.config import get_settings
from app.auth import NHNAuth
from app.collectors.gslb_collector import GSLBCollector
from app.collectors.lb_collector import LoadBalancerCollector
from app.collectors.rds_collector import RDSCollector
from app.collectors.cdn_collector import CDNCollector
from app.collectors.obs_collector import OBSCollector
from app.collectors.instance_collector import InstanceCollector
from app.collectors.service_operations_collector import ServiceOperationsCollector

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()

# 전역 인증 객체
auth = NHNAuth()

# Collector 인스턴스
collectors = {
    "gslb": GSLBCollector(auth),
    "lb": LoadBalancerCollector(auth),
    "rds": RDSCollector(auth),
    "cdn": CDNCollector(auth),
    "obs": OBSCollector(auth),
    "instance": InstanceCollector(auth),
    "service_operations": ServiceOperationsCollector(auth),  # 서비스 운영 지표
}

# 메트릭 캐시
_metrics_cache = None
_cache_timestamp = 0


async def collect_all_metrics():
    """모든 수집기의 메트릭 수집"""
    all_metrics = []
    
    for name, collector in collectors.items():
        try:
            metrics = await collector.collect()
            all_metrics.extend(metrics)
            logger.debug(f"{name} collector: {len(metrics)} metrics collected")
        except Exception as e:
            logger.error(f"{name} collector failed: {e}", exc_info=True)
    
    return all_metrics


class MetricsCollector:
    """Prometheus Collector for NHN Cloud metrics"""
    
    def __init__(self, metric_families):
        self.metric_families = metric_families
    
    def collect(self):
        """Prometheus collector interface"""
        for metric_family in self.metric_families:
            yield metric_family


async def get_cached_metrics():
    """캐시된 메트릭 반환 또는 새로 수집"""
    import time
    
    global _metrics_cache, _cache_timestamp
    
    current_time = time.time()
    cache_ttl = settings.metrics_cache_ttl
    
    # 캐시가 유효하면 반환
    if _metrics_cache and (current_time - _cache_timestamp) < cache_ttl:
        return _metrics_cache
    
    # 새로 수집
    logger.info("Collecting metrics from NHN Cloud APIs...")
    metrics = await collect_all_metrics()
    
    # Prometheus 형식으로 변환
    registry = CollectorRegistry()
    collector = MetricsCollector(metrics)
    registry.register(collector)
    
    # 캐시 업데이트
    _metrics_cache = generate_latest(registry)
    _cache_timestamp = current_time
    
    return _metrics_cache


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan"""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment.value}")
    
    # 초기 메트릭 수집
    try:
        await get_cached_metrics()
        logger.info("Initial metrics collection completed")
    except Exception as e:
        logger.error(f"Initial metrics collection failed: {e}", exc_info=True)
    
    # 백그라운드 메트릭 수집 태스크
    async def background_collector():
        interval = settings.metrics_collection_interval
        while True:
            try:
                await asyncio.sleep(interval)
                await get_cached_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background metrics collection failed: {e}", exc_info=True)
    
    collector_task = asyncio.create_task(background_collector())
    
    yield
    
    # 종료
    collector_task.cancel()
    try:
        await collector_task
    except asyncio.CancelledError:
        pass
    logger.info("Application shutdown")


# FastAPI 앱 생성
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    NHN Cloud Infrastructure Metrics Exporter
    
    Prometheus 형식의 메트릭을 제공하여 NHN Cloud 인프라를 모니터링합니다.
    
    ## 메트릭 전송 방식
    - 메트릭은 `/metrics` HTTP 엔드포인트로 노출됩니다
    - Prometheus 서버가 이 엔드포인트를 스크래핑(Pull)하여 메트릭을 수집합니다
    - 메트릭을 직접 전송(Push)하지 않습니다
    - Prometheus 설정이 필요합니다 (README 참조)
    
    ## 지원 서비스
    - GSLB (DNS Plus)
    - Load Balancer
    - RDS for MySQL
    - CDN
    - Object Storage
    - Compute Instances
    
    ## 서비스 운영 지표 (Service Operations Metrics)
    photo-api 서비스 운영에 필요한 지표:
    - CDN 캐시 효율성 (히트율, 대역폭 사용량)
    - Object Storage 사용량 증가 추이 (사용자 업로드 모니터링)
    - RDS 쿼리 성능 (QPS, Slow Query, 연결 수)
    - Load Balancer 트래픽 분산 효율성
    - GSLB Health Check 실패율 (서비스 가용성)
    """,
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment.value,
        "metrics_endpoint": "/metrics",
        "health_endpoint": "/health",
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint
    
    NHN Cloud 인프라 메트릭을 Prometheus 형식으로 반환합니다.
    """
    try:
        metrics_data = await get_cached_metrics()
        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST
        )
    except Exception as e:
        logger.error(f"Metrics endpoint error: {e}", exc_info=True)
        return Response(
            content="# Error collecting metrics\n",
            media_type=CONTENT_TYPE_LATEST,
            status_code=500
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
