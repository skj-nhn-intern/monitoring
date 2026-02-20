"""
RDS for MySQL Metrics Collector
"""
import logging
from typing import List
import httpx
from prometheus_client.core import GaugeMetricFamily
from app.auth import NHNAuth
from app.config import get_settings

logger = logging.getLogger(__name__)


class RDSCollector:
    """RDS for MySQL 메트릭 수집"""
    
    def __init__(self, auth: NHNAuth):
        self.auth = auth
        self.settings = get_settings()
        self.api_url = self.settings.nhn_rds_api_url
    
    async def collect(self) -> List:
        """RDS 메트릭 수집"""
        if not self.settings.rds_enabled:
            return []
        
        metrics = []
        
        try:
            # RDS API v3 uses X-TC-* headers; fall back to IAM if not configured
            headers = self.auth.get_rds_auth_headers()
            if not headers:
                headers = await self.auth.get_auth_headers(use_iam=True)
            
            # RDS 인스턴스 목록 조회 (v3.0 API)
            url = f"{self.api_url}/rds/api/v3.0/db-instances"
            
            async with httpx.AsyncClient(timeout=self.settings.http_timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                instances = data.get("dbInstances", [])
                
                # 필터링
                instance_ids_filter = []
                if self.settings.rds_instance_ids:
                    instance_ids_filter = [id.strip() for id in self.settings.rds_instance_ids.split(",")]
                
                # RDS 인스턴스 상태 메트릭
                rds_status = GaugeMetricFamily(
                    "nhn_rds_instance_status",
                    "RDS instance status (1=available, 0=other)",
                    labels=["instance_id", "instance_name", "db_engine", "status"]
                )
                
                # RDS 메트릭 통계 조회 (v2.0 API)
                for instance in instances:
                    instance_id = instance.get("dbInstanceId", "")
                    instance_name = instance.get("dbInstanceName", "")
                    db_engine = instance.get("dbEngine", "")
                    status = instance.get("dbInstanceStatus", "")
                    
                    # 필터링
                    if instance_ids_filter and instance_id not in instance_ids_filter:
                        continue
                    
                    # 인스턴스 상태
                    status_value = 1.0 if status == "available" else 0.0
                    rds_status.add_metric(
                        [instance_id, instance_name, db_engine, status],
                        status_value
                    )
                    
                    # 메트릭 통계 조회 (최근 1분 데이터)
                    metrics_url = f"{self.api_url}/rds/api/v2.0/metric-statistics"
                    params = {
                        "dbInstanceId": instance_id,
                        "metricName": "CPU_USAGE,NETWORK_RECV,NETWORK_SENT",
                        "period": "1m",
                        "startTime": "",  # 최신 데이터 조회
                        "endTime": ""
                    }
                    
                    try:
                        metrics_response = await client.get(metrics_url, headers=headers, params=params)
                        metrics_response.raise_for_status()
                        metrics_data = metrics_response.json()
                        
                        # 메트릭 데이터 파싱 및 추가
                        # (실제 응답 형식에 맞게 수정 필요)
                        metric_list = metrics_data.get("metricStatistics", [])
                        for metric_item in metric_list:
                            metric_name = metric_item.get("metricName", "")
                            metric_value = metric_item.get("value", 0.0)
                            
                            # CPU 사용률
                            if metric_name == "CPU_USAGE":
                                if not hasattr(self, "_cpu_usage"):
                                    self._cpu_usage = GaugeMetricFamily(
                                        "nhn_rds_cpu_usage_percent",
                                        "RDS CPU usage percentage",
                                        labels=["instance_id", "instance_name"]
                                    )
                                    metrics.append(self._cpu_usage)
                                self._cpu_usage.add_metric([instance_id, instance_name], metric_value)
                            
                            # 네트워크 수신
                            elif metric_name == "NETWORK_RECV":
                                if not hasattr(self, "_network_recv"):
                                    self._network_recv = GaugeMetricFamily(
                                        "nhn_rds_network_receive_bytes",
                                        "RDS network receive bytes",
                                        labels=["instance_id", "instance_name"]
                                    )
                                    metrics.append(self._network_recv)
                                self._network_recv.add_metric([instance_id, instance_name], metric_value)
                            
                            # 네트워크 송신
                            elif metric_name == "NETWORK_SENT":
                                if not hasattr(self, "_network_sent"):
                                    self._network_sent = GaugeMetricFamily(
                                        "nhn_rds_network_send_bytes",
                                        "RDS network send bytes",
                                        labels=["instance_id", "instance_name"]
                                    )
                                    metrics.append(self._network_sent)
                                self._network_sent.add_metric([instance_id, instance_name], metric_value)
                    except Exception as e:
                        logger.warning(f"RDS 메트릭 통계 조회 실패 (Instance {instance_id}): {e}")
                
                metrics.append(rds_status)
                
        except Exception as e:
            logger.error(f"RDS 메트릭 수집 실패: {e}", exc_info=True)
        
        return metrics
