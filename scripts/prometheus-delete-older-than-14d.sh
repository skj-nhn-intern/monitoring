#!/bin/bash
# Prometheus에서 "현재 시각 기준 14일 이전" 구간만 삭제합니다.
# → 최신 14일 데이터는 유지되고, 그보다 오래된 데이터만 제거됩니다.
#
# 필요: Prometheus에 --web.enable-admin-api 옵션 필요 (docker-compose에 포함됨)
#
# inode 부족 시: delete_series만으로는 블록 디렉터리가 바로 삭제되지 않습니다.
# clean_tombstones 후 재시작하면 compaction 시 오래된 블록이 제거되어 inode가 해제됩니다.
# 서버에서 실행 시: RESTART_PROMETHEUS_AFTER_CLEAN=1 ./scripts/prometheus-delete-older-than-14d.sh
#
# 사용법:
#   1. docker compose up -d prometheus
#   2. chmod +x scripts/prometheus-delete-older-than-14d.sh
#   3. ./scripts/prometheus-delete-older-than-14d.sh
#   4. inode 확보가 급하면: RESTART_PROMETHEUS_AFTER_CLEAN=1 ./scripts/prometheus-delete-older-than-14d.sh
#
set -e
PROM_URL="${PROMETHEUS_URL:-http://localhost:9090}"
RESTART_AFTER="${RESTART_PROMETHEUS_AFTER_CLEAN:-0}"

# 14일 = 14 * 24 * 3600 초
CUTOFF=$(($(date +%s) - 14 * 24 * 3600))
if date -d "@$CUTOFF" &>/dev/null 2>&1; then
  CUTOFF_READABLE=$(date -d "@$CUTOFF" '+%Y-%m-%d %H:%M')
else
  CUTOFF_READABLE=$(date -r "$CUTOFF" '+%Y-%m-%d %H:%M')
fi
echo "삭제 대상: $CUTOFF_READABLE 이전 데이터 (Unix $CUTOFF)"
echo "유지: 최근 14일 데이터"
# match[]={__name__=~".+"} = 모든 시리즈, start=0, end=14일 전 시점
# URL 인코딩: {__name__=~".+"} → %7B__name__%3D~%22.%2B%22%7D
URL="$PROM_URL/api/v1/admin/tsdb/delete_series?match[]=%7B__name__%3D~%22.%2B%22%7D&start=0&end=$CUTOFF"
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$URL")
if [ "$code" = "204" ] || [ "$code" = "200" ]; then
  echo "삭제 요청 완료 (HTTP $code). clean_tombstones 실행 중..."
  ct_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$PROM_URL/api/v1/admin/tsdb/clean_tombstones")
  if [ "$ct_code" != "204" ] && [ "$ct_code" != "200" ]; then
    echo "경고: clean_tombstones HTTP $ct_code"
  fi
  echo "완료. 오래된 블록은 compaction 시 디스크에서 제거됩니다."
  if [ "$RESTART_AFTER" = "1" ]; then
    echo "Prometheus 재시작 중 (compaction으로 inode 확보)..."
    if command -v docker &>/dev/null; then
      docker restart prometheus
      echo "재시작 완료. 수 분 후 compaction이 끝나면 inode 사용량이 줄어듭니다."
    else
      echo "docker를 찾을 수 없습니다. 호스트에서: docker restart prometheus"
    fi
  else
    echo "inode가 부족하면 호스트에서: RESTART_PROMETHEUS_AFTER_CLEAN=1 $0"
  fi
else
  echo "실패 (HTTP $code). Prometheus에 --web.enable-admin-api 가 있는지 확인하세요."
  echo "호스트에서 실행 시 PROMETHEUS_URL=http://127.0.0.1:9090 로 설정하세요."
  exit 1
fi
