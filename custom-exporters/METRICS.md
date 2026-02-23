# NHN Cloud Exporter 메트릭 목록

## 공통 (Exporter)

| 메트릭 이름 | 타입 | 설명 |
|-------------|------|------|
| `nhncloud_exporter_up` | Gauge | Exporter 상태 (1=정상) |
| `nhncloud_exporter_scrape_duration_seconds` | Summary | 수집 소요 시간 (collector별) |
| `nhncloud_exporter_scrape_errors_total` | Counter | 수집 실패 횟수 (collector별) |

## Load Balancer (LB)

| 메트릭 이름 | 타입 | 설명 |
|-------------|------|------|
| `nhncloud_lb` | Info | LB 메타정보 (lb_id) |
| `nhncloud_lb_operating_status` | Gauge | LB 동작 상태 (1=ONLINE) |
| `nhncloud_lb_provisioning_status` | Gauge | 프로비저닝 상태 (1=ACTIVE) |
| `nhncloud_lb_admin_state_up` | Gauge | LB 관리자 Up 여부 |
| `nhncloud_lb_pool_operating_status` | Gauge | 풀 동작 상태 (1=ONLINE) |
| `nhncloud_lb_pool_member_total` | Gauge | 풀 멤버 총 개수 |
| `nhncloud_lb_pool_member_healthy` | Gauge | 정상 멤버 수 |
| `nhncloud_lb_pool_member_unhealthy` | Gauge | 비정상 멤버 수 |
| `nhncloud_lb_member_operating_status` | Gauge | 멤버 동작 상태 (1=ONLINE) |
| `nhncloud_lb_member_admin_state_up` | Gauge | 멤버 관리자 Up |
| `nhncloud_lb_member_weight` | Gauge | 멤버 가중치 |
| `nhncloud_lb_healthmonitor_admin_state_up` | Gauge | 헬스모니터 관리자 상태 |
| `nhncloud_lb_healthmonitor_delay_seconds` | Gauge | 헬스체크 간격(초) |
| `nhncloud_lb_healthmonitor_timeout_seconds` | Gauge | 헬스체크 타임아웃(초) |
| `nhncloud_lb_healthmonitor_max_retries` | Gauge | 최대 재시도 횟수 |
| `nhncloud_lb_listener_connection_limit` | Gauge | 리스너 연결 제한 |
| `nhncloud_lb_listener_cert_expire_days` | Gauge | TLS 인증서 만료까지 일수 |

## RDS (MySQL)

| 메트릭 이름 | 타입 | 설명 |
|-------------|------|------|
| `nhncloud_rds_up` | Gauge | RDS API 수집 성공 여부 (1=성공) |
| `nhncloud_rds_instances` | Gauge | API로 조회된 DB 인스턴스 수 |
| `nhncloud_rds_instance_status` | Gauge | 인스턴스 상태 (1=AVAILABLE, 2=FAIL_OVER, 3=STOPPED, 4=ERROR, 0=기타) |
| `nhncloud_rds_instance_ha_enabled` | Gauge | HA 사용 여부 (1=사용) |
| `nhncloud_rds_replication_type` | Gauge | 복제 타입 (1=STANDALONE, 2=HA, 3=READ_REPLICA) |
| `nhncloud_rds_instance_port` | Gauge | DB 포트 |
| `nhncloud_rds_deletion_protection` | Gauge | 삭제 보호 여부 |
| `nhncloud_rds_need_param_group_apply` | Gauge | 파라미터 그룹 적용 필요 여부 |
| `nhncloud_rds_need_migration` | Gauge | 마이그레이션 필요 여부 |
| `nhncloud_rds_backup_status` | Gauge | 백업 상태 (1=COMPLETED, 2=IN_PROGRESS, 3=FAILED) |
| `nhncloud_rds_backup_size_bytes` | Gauge | 백업 크기(바이트) |
| `nhncloud_rds_backup_latest_age_seconds` | Gauge | 마지막 성공 백업 이후 경과 시간(초) |
| `nhncloud_rds_backup_count` | Gauge | 백업 개수 (인스턴스·타입별) |
| `nhncloud_rds_backup_retention_period_days` | Gauge | 백업 보관 기간(일) |

## CDN

| 메트릭 이름 | 타입 | 설명 |
|-------------|------|------|
| `nhncloud_cdn_health_check_up` | Gauge | CDN URL 상태 (1=정상, 0=실패) |
| `nhncloud_cdn_health_check_duration_seconds` | Gauge | CDN URL 요청 소요 시간(초) |

## Object Storage (OBS)

| 메트릭 이름 | 타입 | 설명 |
|-------------|------|------|
| `nhn_obs_health_check_up` | Gauge | OBS 헬스체크 (1=up, 0=down) |
| `nhn_obs_health_check_duration_seconds` | Gauge | OBS 헬스체크 소요 시간(초) |
