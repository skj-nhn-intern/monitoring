# monitoring

메트릭·로그·알림을 위한 모니터링 스택 (Prometheus, Pushgateway, Alertmanager, Loki, Grafana, Promtail).

## 구성

| 서비스        | 포트  | 설명 |
|---------------|-------|------|
| **Prometheus** | 9090 | 메트릭 수집·저장·쿼리 |
| **Pushgateway** (프록시) | 9091 | 단기/배치 작업 메트릭 push (PUT→POST 변환 지원) |
| **Alertmanager** | 9093 | 알림 라우팅·그룹핑·침묵 |
| **Dooray 웹훅 어댑터** | 9095 | Alertmanager → Dooray 채널 전달 |
| **Loki**      | 3100 | 로그 저장·쿼리 |
| **Grafana**   | 3000 | 대시보드·메트릭/로그 시각화 |
| **Promtail**  | -    | 로그 수집 후 Loki로 전송 |

## 실행

```bash
docker compose up -d
```

## 접속

- **Prometheus**: http://localhost:9090  
- **Pushgateway**: http://localhost:9091  
- **Alertmanager**: http://localhost:9093  
- **Grafana**: http://localhost:3000 (기본 로그인: admin / admin)

## 설정

- `config/prometheus.yml` — Prometheus 스크랩·알림 타겟
- `config/alertmanager.yml` — Alertmanager 라우팅·수신자 (Dooray 등)

### Dooray 채널로 알림 받기 (중요/위험도별)

1. **Dooray 메신저에서 인커밍 웹훅 발급**
   - 보낼 채널에서 **알림봇** 또는 **인커밍 웹훅** 연동 메뉴로 들어가 웹훅 URL을 복사합니다.
   - 위험(critical)용 채널, 중요(warning)용 채널 각각 URL을 준비할 수 있습니다.

2. **환경 변수 설정**
   - 프로젝트 루트에 `.env` 파일을 만들고 아래처럼 넣습니다.
   ```bash
   # 위험 알림을 보낼 Dooray 채널 웹훅 URL (예: https://hook.dooray.com/services/...)
   DOORAY_HOOK_URL_CRITICAL=https://hook.dooray.com/services/xxx/yyy/zzz
   # 중요 알림을 보낼 Dooray 채널 웹훅 URL
   DOORAY_HOOK_URL_WARNING=https://hook.dooray.com/services/xxx/yyy/zzz
   ```
   - 같은 채널로 보내려면 두 값을 같은 URL로 설정하면 됩니다.

3. **재기동**
   ```bash
   docker compose up -d --build
   ```
   - Prometheus 알림 규칙에서 `severity: critical` / `severity: warning` 라벨을 사용하면 해당 채널로 전달됩니다.

## Pushgateway 사용 예 (배치/단기 작업)

- **9091** 포트는 Pushgateway 앞단 **프록시**가 받습니다. **POST**와 **PUT** 모두 지원( PUT은 내부에서 POST로 변환 )합니다.
- Prometheus는 Pushgateway를 직접 스크랩하므로 동작에는 변경이 없습니다.

```bash
# 단일 메트릭 push (POST)
echo "my_metric 123" | curl --data-binary @- -X POST http://localhost:9091/metrics/job/my_job/instance/my_instance
# PUT으로 보내도 프록시가 POST로 변환하여 Pushgateway에 전달
echo "my_metric 123" | curl --data-binary @- -X PUT http://localhost:9091/metrics/job/my_job/instance/my_instance
```

Grafana에서 Prometheus를 데이터 소스로 추가하면 메트릭 대시보드를 만들 수 있습니다.
