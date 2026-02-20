"""
Service Operations Metrics Collector
photo-api 서비스 운영에 필요한 NHN Cloud 인프라 지표 수집

서비스 운영 관점의 지표:
1. CDN 캐시 효율성 (히트율, 대역폭 사용량)
2. Object Storage 사용량 증가 추이 (사용자 업로드 추이)
3. RDS 쿼리 성능 (QPS, Slow Query, 연결 수)
4. Load Balancer 트래픽 분산 효율성
5. GSLB Health Check 실패율 (서비스 가용성)
"""
import logging
from typing import List, Dict, Optional
import httpx
from datetime import datetime, timedelta
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
from app.auth import NHNAuth
from app.config import get_settings

logger = logging.getLogger(__name__)


class ServiceOperationsCollector:
    """서비스 운영 지표 수집"""
    
    def __init__(self, auth: NHNAuth):
        self.auth = auth
        self.settings = get_settings()
    
    async def collect(self) -> List:
        """서비스 운영 메트릭 수집"""
        if not self.settings.service_operations_enabled:
            return []
        
        metrics = []
        
        try:
            # 1. CDN 운영 지표 (캐시 효율성, 대역폭)
            if self.settings.photo_api_cdn_app_key:
                cdn_metrics = await self._collect_cdn_operations()
                metrics.extend(cdn_metrics)
            
            # 2. Object Storage 운영 지표 (사용량 증가 추이)
            if self.settings.photo_api_obs_container:
                obs_metrics = await self._collect_obs_operations()
                metrics.extend(obs_metrics)
            
            # 3. RDS 운영 지표 (쿼리 성능, 연결 수)
            if self.settings.photo_api_rds_instance_id:
                rds_metrics = await self._collect_rds_operations()
                metrics.extend(rds_metrics)
            
            # 4. Load Balancer 운영 지표 (트래픽 분산 효율성)
            if self.settings.photo_api_lb_ids:
                lb_metrics = await self._collect_lb_operations()
                metrics.extend(lb_metrics)
            
            # 5. GSLB 운영 지표 (Health Check 실패율)
            if self.settings.gslb_enabled:
                gslb_metrics = await self._collect_gslb_operations()
                metrics.extend(gslb_metrics)
            
        except Exception as e:
            logger.error(f"서비스 운영 메트릭 수집 실패: {e}", exc_info=True)
        
        return metrics
    
    async def _collect_cdn_operations(self) -> List:
        """CDN 운영 지표: 캐시 효율성, 대역폭 사용량"""
        metrics = []
        
        try:
            appkey = self.auth.get_appkey(service="cdn")
            headers = await self.auth.get_auth_headers(use_iam=False, service="cdn")
            
            api_url = self.settings.nhn_cdn_api_url
            
            cdn_app_key = self.settings.photo_api_cdn_app_key
            if not cdn_app_key:
                logger.warning("Photo API CDN App Key가 설정되지 않았습니다.")
                return metrics
            
            async with httpx.AsyncClient(timeout=self.settings.http_timeout) as client:
                # CDN 서비스 조회
                services_url = f"{api_url}/v2.0/appKeys/{appkey}/services"
                
                response = await client.get(services_url, headers=headers)
                if response.status_code == 404:
                    logger.warning("CDN 서비스 목록 404 - CDN 미사용 시 정상입니다.")
                    return metrics
                response.raise_for_status()
                data = response.json()
                
                services = data.get("services", [])
                
                # Photo API CDN 서비스 찾기 (AppKey로 식별)
                photo_api_cdn_service = None
                for service in services:
                    if service.get("appKey") == cdn_app_key:
                        photo_api_cdn_service = service
                        break
                
                if not photo_api_cdn_service:
                    logger.warning(f"Photo API CDN 서비스를 찾을 수 없습니다: {cdn_app_key}")
                    return metrics
                
                # 서비스 정보 추출 (serviceId가 있으면 사용, 없으면 다른 필드 사용)
                service_id = photo_api_cdn_service.get("serviceId") or photo_api_cdn_service.get("id") or cdn_app_key
                service_name = photo_api_cdn_service.get("serviceName") or photo_api_cdn_service.get("name") or ""
                
                # CDN 통계 조회 (캐시 히트율, 대역폭 등)
                # 실제 API 엔드포인트는 NHN Cloud 문서 확인 필요
                # 예시: /v2.0/appKeys/{appkey}/services/{serviceId}/statistics
                stats_url = f"{api_url}/v2.0/appKeys/{appkey}/services/{service_id}/statistics"
                
                # 통계 기간 설정 (최근 1시간)
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(hours=1)
                
                params = {
                    "startTime": start_time.isoformat() + "Z",
                    "endTime": end_time.isoformat() + "Z",
                    "interval": "1h"
                }
                
                try:
                    stats_response = await client.get(stats_url, headers=headers, params=params)
                    stats_response.raise_for_status()
                    stats_data = stats_response.json()
                    
                    # CDN 캐시 히트율
                    cache_hit_rate = GaugeMetricFamily(
                        "photo_api_cdn_cache_hit_rate",
                        "Photo API CDN cache hit rate (0-1)",
                        labels=["service_id", "service_name"]
                    )
                    
                    # CDN 대역폭 사용량
                    bandwidth_usage = GaugeMetricFamily(
                        "photo_api_cdn_bandwidth_bytes",
                        "Photo API CDN bandwidth usage in bytes",
                        labels=["service_id", "service_name", "direction"]  # direction: in | out
                    )
                    
                    # CDN 요청 수
                    request_count = CounterMetricFamily(
                        "photo_api_cdn_requests_total",
                        "Photo API CDN total requests",
                        labels=["service_id", "service_name", "status"]  # status: hit | miss
                    )
                    
                    # 실제 응답 형식에 맞게 파싱 (예시)
                    statistics = stats_data.get("statistics", [])
                    for stat in statistics:
                        # 캐시 히트율 계산
                        cache_hits = stat.get("cacheHits", 0)
                        cache_misses = stat.get("cacheMisses", 0)
                        total_requests = cache_hits + cache_misses
                        
                        if total_requests > 0:
                            hit_rate = cache_hits / total_requests
                            cache_hit_rate.add_metric(
                                [service_id, service_name or service_id],
                                hit_rate
                            )
                        
                        # 대역폭 사용량
                        bandwidth_in = stat.get("bandwidthIn", 0)
                        bandwidth_out = stat.get("bandwidthOut", 0)
                        bandwidth_usage.add_metric(
                            [service_id, service_name or service_id, "in"],
                            float(bandwidth_in)
                        )
                        bandwidth_usage.add_metric(
                            [service_id, service_name or service_id, "out"],
                            float(bandwidth_out)
                        )
                        
                        # 요청 수
                        request_count.add_metric(
                            [service_id, service_name or service_id, "hit"],
                            cache_hits
                        )
                        request_count.add_metric(
                            [service_id, service_name or service_id, "miss"],
                            cache_misses
                        )
                    
                    if cache_hit_rate.samples:
                        metrics.append(cache_hit_rate)
                    if bandwidth_usage.samples:
                        metrics.append(bandwidth_usage)
                    if request_count.samples:
                        metrics.append(request_count)
                        
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        logger.debug("CDN 통계 API를 사용할 수 없습니다 (서비스별로 다를 수 있음)")
                    else:
                        logger.warning(f"CDN 통계 조회 실패: {e}")
                except Exception as e:
                    logger.warning(f"CDN 통계 조회 중 오류: {e}")
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 404):
                logger.warning("CDN 운영 지표 404/403 - CDN 미사용 시 정상입니다.")
            else:
                logger.error(f"CDN 운영 지표 수집 실패: {e.response.status_code}")
        except Exception as e:
            logger.error(f"CDN 운영 지표 수집 실패: {e}", exc_info=True)
        
        return metrics
    
    async def _collect_obs_operations(self) -> List:
        """Object Storage 운영 지표: 사용량 증가 추이"""
        metrics = []
        
        try:
            # OBS 전용 API 비밀번호가 있으면 그걸로 토큰 발급
            token = await self.auth.get_iam_token(use_obs_password=True)
            container_name = self.settings.photo_api_obs_container
            
            base_url = self.auth.get_obs_storage_url()
            if base_url:
                base_url = base_url.rstrip("/")
                container_info_url = f"{base_url}/{container_name}"
            else:
                tenant_id = self.settings.nhn_tenant_id
                account = f"AUTH_{tenant_id}"
                api_url = self.settings.nhn_obs_api_url
                container_info_url = f"{api_url}/v1/{account}/{container_name}"
            
            async with httpx.AsyncClient(timeout=self.settings.http_timeout) as client:
                info_response = await client.head(
                    container_info_url,
                    headers={"X-Auth-Token": token}
                )
                if info_response.status_code == 403:
                    logger.warning("Object Storage 운영 지표 403 - API 비밀번호·권한을 확인하세요.")
                    return metrics
                if info_response.status_code == 404:
                    logger.warning(f"Photo API 컨테이너를 찾을 수 없습니다: {container_name}")
                    return metrics
                info_response.raise_for_status()
                
                # 현재 사용량
                bytes_used = int(info_response.headers.get("X-Container-Bytes-Used", 0))
                object_count = int(info_response.headers.get("X-Container-Object-Count", 0))
                
                # Object Storage 사용량 (사용자 업로드 추이 모니터링)
                obs_storage = GaugeMetricFamily(
                    "photo_api_obs_storage_bytes",
                    "Photo API Object Storage usage in bytes (monitors user upload trend)",
                    labels=["container_name", "service"]
                )
                obs_storage.add_metric(
                    [container_name, "photo-api"],
                    float(bytes_used)
                )
                
                # 객체 수 (업로드된 사진 수 추정)
                obs_objects = GaugeMetricFamily(
                    "photo_api_obs_object_count",
                    "Photo API Object Storage object count (estimated photo count)",
                    labels=["container_name", "service"]
                )
                obs_objects.add_metric(
                    [container_name, "photo-api"],
                    float(object_count)
                )
                
                metrics.extend([obs_storage, obs_objects])
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 404):
                logger.warning("Object Storage 운영 지표 403/404 - API 비밀번호·권한을 확인하세요.")
            else:
                logger.error(f"Object Storage 운영 지표 수집 실패: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Object Storage 운영 지표 수집 실패: {e}", exc_info=True)
        
        return metrics
    
    async def _collect_rds_operations(self) -> List:
        """RDS 운영 지표: 쿼리 성능, 연결 수"""
        metrics = []
        
        try:
            headers = self.auth.get_rds_auth_headers()
            if not headers:
                headers = await self.auth.get_auth_headers(use_iam=True)
            instance_id = self.settings.photo_api_rds_instance_id
            
            api_url = self.settings.nhn_rds_api_url
            
            # RDS 메트릭 통계 조회
            metrics_url = f"{api_url}/rds/api/v2.0/metric-statistics"
            
            # 최근 1분 데이터
            params = {
                "dbInstanceId": instance_id,
                "metricName": "CPU_USAGE,NETWORK_RECV,NETWORK_SENT,QPS,SLOW_QUERY_COUNT,CURRENT_CONNECTIONS",
                "period": "1m",
            }
            
            async with httpx.AsyncClient(timeout=self.settings.http_timeout) as client:
                response = await client.get(metrics_url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                metric_list = data.get("metricStatistics", [])
                
                # RDS CPU 사용률
                rds_cpu = GaugeMetricFamily(
                    "photo_api_rds_cpu_usage_percent",
                    "Photo API RDS CPU usage percentage (query performance indicator)",
                    labels=["instance_id", "service"]
                )
                
                # RDS QPS (Queries Per Second)
                rds_qps = GaugeMetricFamily(
                    "photo_api_rds_qps",
                    "Photo API RDS queries per second (database load indicator)",
                    labels=["instance_id", "service"]
                )
                
                # RDS Slow Query 수
                rds_slow_query = GaugeMetricFamily(
                    "photo_api_rds_slow_query_count",
                    "Photo API RDS slow query count (performance issue indicator)",
                    labels=["instance_id", "service"]
                )
                
                # RDS 현재 연결 수
                rds_connections = GaugeMetricFamily(
                    "photo_api_rds_current_connections",
                    "Photo API RDS current connections (connection pool usage)",
                    labels=["instance_id", "service"]
                )
                
                # RDS 네트워크 트래픽
                rds_network_recv = GaugeMetricFamily(
                    "photo_api_rds_network_receive_bytes",
                    "Photo API RDS network receive bytes",
                    labels=["instance_id", "service"]
                )
                
                rds_network_sent = GaugeMetricFamily(
                    "photo_api_rds_network_send_bytes",
                    "Photo API RDS network send bytes",
                    labels=["instance_id", "service"]
                )
                
                for metric_item in metric_list:
                    metric_name = metric_item.get("metricName", "")
                    metric_value = metric_item.get("value", 0.0)
                    
                    if metric_name == "CPU_USAGE":
                        rds_cpu.add_metric([instance_id, "photo-api"], metric_value)
                    elif metric_name == "QPS":
                        rds_qps.add_metric([instance_id, "photo-api"], metric_value)
                    elif metric_name == "SLOW_QUERY_COUNT":
                        rds_slow_query.add_metric([instance_id, "photo-api"], metric_value)
                    elif metric_name == "CURRENT_CONNECTIONS":
                        rds_connections.add_metric([instance_id, "photo-api"], metric_value)
                    elif metric_name == "NETWORK_RECV":
                        rds_network_recv.add_metric([instance_id, "photo-api"], metric_value)
                    elif metric_name == "NETWORK_SENT":
                        rds_network_sent.add_metric([instance_id, "photo-api"], metric_value)
                
                # 샘플이 있는 메트릭만 추가
                if rds_cpu.samples:
                    metrics.append(rds_cpu)
                if rds_qps.samples:
                    metrics.append(rds_qps)
                if rds_slow_query.samples:
                    metrics.append(rds_slow_query)
                if rds_connections.samples:
                    metrics.append(rds_connections)
                if rds_network_recv.samples:
                    metrics.append(rds_network_recv)
                if rds_network_sent.samples:
                    metrics.append(rds_network_sent)
                
        except Exception as e:
            logger.error(f"RDS 운영 지표 수집 실패: {e}", exc_info=True)
        
        return metrics
    
    async def _collect_lb_operations(self) -> List:
        """Load Balancer 운영 지표: 트래픽 분산 효율성"""
        metrics = []
        
        try:
            headers = await self.auth.get_auth_headers(use_iam=True)
            lb_ids = [id.strip() for id in self.settings.photo_api_lb_ids.split(",") if id.strip()]
            
            if not lb_ids:
                return metrics
            
            api_url = self.settings.nhn_lb_api_url
            
            async with httpx.AsyncClient(timeout=self.settings.http_timeout) as client:
                # Load Balancer별 Pool Member 상태 조회
                lb_member_health = GaugeMetricFamily(
                    "photo_api_lb_pool_member_health_ratio",
                    "Photo API Load Balancer pool member health ratio (0-1, 1=all healthy)",
                    labels=["lb_id", "lb_name", "pool_id", "pool_name"]
                )
                
                for lb_id in lb_ids:
                    # Load Balancer 정보 조회
                    lb_url = f"{api_url}/v2.0/lbaas/loadbalancers/{lb_id}"
                    try:
                        lb_response = await client.get(lb_url, headers=headers)
                        if lb_response.status_code == 401:
                            # 토큰 만료 가능성 - 토큰 갱신 후 재시도
                            logger.warning(f"Load Balancer {lb_id} 401 - 토큰 갱신 후 재시도합니다.")
                            self.auth._token = None
                            self.auth._token_expires = None
                            headers = await self.auth.get_auth_headers(use_iam=True)
                            lb_response = await client.get(lb_url, headers=headers)
                        lb_response.raise_for_status()
                        lb_data = lb_response.json()
                        lb = lb_data.get("loadbalancer", {})
                        lb_name = lb.get("name", "")
                        
                        # Pool 조회
                        pools_url = f"{api_url}/v2.0/lbaas/pools?loadbalancer_id={lb_id}"
                        pools_response = await client.get(pools_url, headers=headers)
                        if pools_response.status_code == 401:
                            self.auth._token = None
                            self.auth._token_expires = None
                            headers = await self.auth.get_auth_headers(use_iam=True)
                            pools_response = await client.get(pools_url, headers=headers)
                        pools_response.raise_for_status()
                        pools_data = pools_response.json()
                        pools = pools_data.get("pools", [])
                        
                        for pool in pools:
                            pool_id = pool.get("id", "")
                            pool_name = pool.get("name", "")
                            
                            # Pool Member 조회
                            members_url = f"{api_url}/v2.0/lbaas/pools/{pool_id}/members"
                            members_response = await client.get(members_url, headers=headers)
                            if members_response.status_code == 401:
                                self.auth._token = None
                                self.auth._token_expires = None
                                headers = await self.auth.get_auth_headers(use_iam=True)
                                members_response = await client.get(members_url, headers=headers)
                            members_response.raise_for_status()
                            members_data = members_response.json()
                            members = members_data.get("members", [])
                            
                            # 건강한 멤버 비율 계산
                            total_members = len(members)
                            healthy_members = sum(1 for m in members if m.get("monitor_status") == "ONLINE")
                            
                            if total_members > 0:
                                health_ratio = healthy_members / total_members
                                lb_member_health.add_metric(
                                    [lb_id, lb_name, pool_id, pool_name],
                                    health_ratio
                                )
                    except Exception as e:
                        logger.warning(f"Load Balancer {lb_id} 조회 실패: {e}")
                
                if lb_member_health.samples:
                    metrics.append(lb_member_health)
                
        except Exception as e:
            logger.error(f"Load Balancer 운영 지표 수집 실패: {e}", exc_info=True)
        
        return metrics
    
    async def _collect_gslb_operations(self) -> List:
        """GSLB 운영 지표: Health Check 실패율"""
        metrics = []
        
        try:
            appkey = self.auth.get_appkey(service="dnsplus")
            headers = await self.auth.get_auth_headers(use_iam=False, service="dnsplus")
            
            api_url = self.settings.nhn_dnsplus_api_url
            
            async with httpx.AsyncClient(timeout=self.settings.http_timeout) as client:
                # GSLB 목록 조회
                gslbs_url = f"{api_url}/dnsplus/v1.0/appkeys/{appkey}/gslbs"
                gslbs_response = await client.get(gslbs_url, headers=headers)
                gslbs_response.raise_for_status()
                gslbs_data = gslbs_response.json()
                gslbs = gslbs_data.get("gslbs", [])
                
                # GSLB Pool Member Health Check 실패율
                gslb_health_failure_rate = GaugeMetricFamily(
                    "photo_api_gslb_pool_member_health_failure_rate",
                    "Photo API GSLB pool member health check failure rate (0-1, 0=all healthy)",
                    labels=["gslb_id", "gslb_name", "pool_id", "pool_name"]
                )
                
                for gslb in gslbs:
                    gslb_id = gslb.get("gslbId", "")
                    gslb_name = gslb.get("gslbName", "")
                    
                    # Pool 조회
                    pools_url = f"{api_url}/dnsplus/v1.0/appkeys/{appkey}/gslbs/{gslb_id}/pools"
                    try:
                        pools_response = await client.get(pools_url, headers=headers)
                        pools_response.raise_for_status()
                        pools_data = pools_response.json()
                        pools = pools_data.get("pools", [])
                        
                        for pool in pools:
                            pool_id = pool.get("poolId", "")
                            pool_name = pool.get("poolName", "")
                            
                            # Pool Member 조회
                            members = pool.get("members", [])
                            total_members = len(members)
                            unhealthy_members = sum(
                                1 for m in members 
                                if m.get("operatingStatus") != "ONLINE"
                            )
                            
                            if total_members > 0:
                                failure_rate = unhealthy_members / total_members
                                gslb_health_failure_rate.add_metric(
                                    [gslb_id, gslb_name, pool_id, pool_name],
                                    failure_rate
                                )
                    except Exception as e:
                        logger.warning(f"GSLB {gslb_id} Pool 조회 실패: {e}")
                
                if gslb_health_failure_rate.samples:
                    metrics.append(gslb_health_failure_rate)
                
        except Exception as e:
            logger.error(f"GSLB 운영 지표 수집 실패: {e}", exc_info=True)
        
        return metrics
