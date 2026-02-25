# NHN Cloud Exporter 메트릭 목록

## 공통 (Exporter)

| 메트릭 이름 | 타입 | 라벨 | 설명 |
|-------------|------|------|------|
| `nhncloud_exporter_up` | Gauge | - | Exporter 상태 (1=정상) |
| `nhncloud_exporter_scrape_duration_seconds` | Summary | `collector` | 수집 소요 시간(초) |
| `nhncloud_exporter_scrape_errors_total` | Counter | `collector` | 수집 실패 횟수 |

## Load Balancer (LB)

| 메트릭 이름 | 타입 | 라벨 | 설명 |
|-------------|------|------|------|
| `nhncloud_lb` | Info | `lb_id` | LB 메타정보 (name, vip_address, provider, description) |
| `nhncloud_lb_operating_status` | Gauge | `lb_id`, `lb_name` | LB 동작 상태 (1=ONLINE, 0=기타) |
| `nhncloud_lb_provisioning_status` | Gauge | `lb_id`, `lb_name` | 프로비저닝 상태 (1=ACTIVE, 0=기타) |
| `nhncloud_lb_admin_state_up` | Gauge | `lb_id`, `lb_name` | LB 관리자 Up (1/0) |
| `nhncloud_lb_stats_active_connections` | Gauge | `lb_id`, `lb_name` | 현재 활성 연결 수 (Octavia stats API) |
| `nhncloud_lb_stats_total_connections` | Gauge | `lb_id`, `lb_name` | 누적 처리 연결 수 |
| `nhncloud_lb_stats_bytes_in` | Gauge | `lb_id`, `lb_name` | 누적 수신 바이트 |
| `nhncloud_lb_stats_bytes_out` | Gauge | `lb_id`, `lb_name` | 누적 송신 바이트 |
| `nhncloud_lb_stats_request_errors` | Gauge | `lb_id`, `lb_name` | 요청 에러 수 |
| `nhncloud_lb_pool` | Info | `pool_id`, `pool_name`, `lb_name` | 풀 메타정보 (protocol, lb_algorithm) |
| `nhncloud_lb_pool_operating_status` | Gauge | `pool_id`, `pool_name`, `lb_name` | 풀 동작 상태 (1=ONLINE, 0=기타) |
| `nhncloud_lb_pool_member_total` | Gauge | `pool_id`, `pool_name`, `lb_name` | 풀 멤버 총 개수 |
| `nhncloud_lb_pool_member_healthy` | Gauge | `pool_id`, `pool_name`, `lb_name` | 정상 멤버 수 (operating_status=ONLINE 또는 ACTIVE) |
| `nhncloud_lb_pool_member_unhealthy` | Gauge | `pool_id`, `pool_name`, `lb_name` | 비정상 멤버 수 |
| `nhncloud_lb_member_operating_status` | Gauge | `pool_id`, `pool_name`, `member_id`, `member_address`, `member_port`, `lb_name` | **현재 실행 중인 멤버만** (1=ONLINE/ACTIVE, 매 스크래핑 갱신·추이 반영) |
| `nhncloud_lb_member_admin_state_up` | Gauge | `pool_id`, `pool_name`, `member_id`, `member_address`, `member_port`, `lb_name` | **현재 실행 중인 멤버만** (1=up, 매 스크래핑 갱신·추이 반영) |
| `nhncloud_lb_member_weight` | Gauge | `pool_id`, `pool_name`, `member_id`, `member_address`, `member_port`, `lb_name` | **현재 실행 중인 멤버만** (가중치, 매 스크래핑 갱신·추이 반영) |
| `nhncloud_lb_healthmonitor_admin_state_up` | Gauge | `hm_id`, `pool_id` | 헬스모니터 관리자 상태 (1/0) |
| `nhncloud_lb_healthmonitor_delay_seconds` | Gauge | `hm_id`, `pool_id` | 헬스체크 간격(초) |
| `nhncloud_lb_healthmonitor_timeout_seconds` | Gauge | `hm_id`, `pool_id` | 헬스체크 타임아웃(초) |
| `nhncloud_lb_healthmonitor_max_retries` | Gauge | `hm_id`, `pool_id` | 최대 재시도 횟수 |
| `nhncloud_lb_listener` | Info | `listener_id`, `lb_name` | 리스너 메타정보 (protocol, port, default_pool_id) |
| `nhncloud_lb_listener_connection_limit` | Gauge | `listener_id`, `protocol`, `port`, `lb_name` | 리스너 연결 제한 |
| `nhncloud_lb_listener_cert_expire_days` | Gauge | `listener_id`, `lb_name` | TLS 인증서 만료까지 일수 |

**멤버 메트릭 (member_operating_status, member_admin_state_up, member_weight)**  
- **현재 실행 중인 멤버만** 노출: `operating_status`가 ONLINE/ACTIVE 이고 `admin_state_up`가 true인 멤버만 시리즈로 내보냅니다.  
- 매 스크래핑 시 해당 풀의 기존 멤버 시리즈를 제거한 뒤 실행 중인 멤버만 다시 설정하므로, 멤버가 내려가면 시리즈가 사라지고 올라오면 다시 나타나 **추이(트렌드)**를 볼 수 있습니다.  
- 풀 단위 집계는 기존대로 `nhncloud_lb_pool_member_total` / `_healthy` / `_unhealthy`로 전체·정상·비정상 개수 추이 확인 가능합니다.

## RDS (MySQL)

| 메트릭 이름 | 타입 | 라벨 | 설명 |
|-------------|------|------|------|
| `nhncloud_rds_up` | Gauge | - | RDS API 수집 성공 여부 (1=성공) |
| `nhncloud_rds_instances` | Gauge | - | API로 조회된 DB 인스턴스 수 |
| `nhncloud_rds_instance_status` | Gauge | `db_instance_id`, `db_instance_name`, `db_version`, `db_instance_type` | 인스턴스 상태 (1=AVAILABLE, 2=FAIL_OVER, 3=STOPPED, 4=ERROR, 0=기타) |
| `nhncloud_rds_instance_ha_enabled` | Gauge | `db_instance_id`, `db_instance_name` | HA 사용 여부 (1=사용, 0=미사용) |
| `nhncloud_rds_replication_type` | Gauge | `db_instance_group_id`, `db_instance_name` | 복제 타입 (1=STANDALONE, 2=HIGH_AVAILABILITY, 3=READ_REPLICA, 0=UNKNOWN) |
| `nhncloud_rds_instance_port` | Gauge | `db_instance_id`, `db_instance_name` | DB 포트 |
| `nhncloud_rds_deletion_protection` | Gauge | `db_instance_id`, `db_instance_name` | 삭제 보호 여부 (1/0) |
| `nhncloud_rds_need_param_group_apply` | Gauge | `db_instance_id`, `db_instance_name` | 파라미터 그룹 적용 필요 (1/0) |
| `nhncloud_rds_need_migration` | Gauge | `db_instance_id`, `db_instance_name` | 마이그레이션 필요 (1/0) |
| `nhncloud_rds_backup_status` | Gauge | `backup_id`, `db_instance_id`, `db_instance_name`, `backup_type` | 백업 상태 (1=COMPLETED, 2=IN_PROGRESS, 3=FAILED, 0=기타) |
| `nhncloud_rds_backup_size_bytes` | Gauge | `backup_id`, `db_instance_id`, `db_instance_name`, `backup_type` | 백업 크기(바이트) |
| `nhncloud_rds_backup_latest_age_seconds` | Gauge | `db_instance_id`, `db_instance_name` | 마지막 성공 백업 이후 경과 시간(초) |
| `nhncloud_rds_backup_count` | Gauge | `db_instance_id`, `db_instance_name`, `backup_type` | 백업 개수 |
| `nhncloud_rds_backup_retention_period_days` | Gauge | `db_instance_id`, `db_instance_name` | 백업 보관 기간(일) |

## CDN

| 메트릭 이름 | 타입 | 라벨 | 설명 |
|-------------|------|------|------|
| `nhncloud_cdn_health_check_up` | Gauge | `target` | CDN URL 상태 (1=정상, 0=실패) |
| `nhncloud_cdn_health_check_duration_seconds` | Gauge | `target` | CDN URL 요청 소요 시간(초) |

## Object Storage (OBS)

| 메트릭 이름 | 타입 | 라벨 | 설명 |
|-------------|------|------|------|
| `nhn_obs_health_check_up` | Gauge | `region`, `target` | OBS 헬스체크 (1=up, 0=down) |
| `nhn_obs_health_check_duration_seconds` | Gauge | `region`, `target` | OBS 헬스체크 소요 시간(초) |
