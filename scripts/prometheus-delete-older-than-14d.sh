#!/bin/bash
# Prometheus에서 "현재 시각 기준 14일 이전" 구간만 삭제합니다.
# → 최신 14일 데이터는 유지되고, 그보다 오래된 데이터만 제거됩니다.
#
# 필요: Prometheus에 --web.enable-admin-api 옵션 필요 (docker-compose에 포함됨)
#
# 사용법:
#   1. docker compose up -d prometheus
#   2. chmod +x scripts/prometheus-delete-older-than-14d.sh
#   3. ./scripts/prometheus-delete-older-than-14d.sh
#
set -e
PROM_URL="${PROMETHEUS_URL:-http://prometheus:9090}"
# 14일 = 14 * 24 * 3600 초
CUTOFF=$(($(date +%s) - 14 * 24 * 3600))
if date -d "@$CUTOFF" &>/dev/null; then
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
  curl -s -X POST "$PROM_URL/api/v1/admin/tsdb/clean_tombstones"
  echo ""
  echo "완료. 오래된 데이터는 compaction 시 디스크에서 제거됩니다."
else
  echo "실패 (HTTP $code). Prometheus에 --web.enable-admin-api 가 있는지 확인하세요."
  exit 1
fi
