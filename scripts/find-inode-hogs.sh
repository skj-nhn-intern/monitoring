#!/bin/bash
# inode를 가장 많이 쓰는 상위 경로를 출력합니다.
# 서버에서 df -i 로 100% 나오면 이 스크립트를 실행해 원인 디렉터리를 확인하세요.
#
# 사용법 (모니터링 서버에서):
#   chmod +x scripts/find-inode-hogs.sh
#   sudo ./scripts/find-inode-hogs.sh
#
set -e
echo "=== inode 사용량 상위 경로 (파일 개수 기준) ==="
echo ""

# 루트 기준, 다른 파티션 제외(-xdev), 경로 depth 4까지 묶어서 카운트
if command -v find &>/dev/null; then
  find / -xdev -type f 2>/dev/null | awk -F/ 'NF>=4 {p="/"; for(i=2;i<=4;i++) p=p $i "/"; print p}' | sort | uniq -c | sort -rn | head -25
else
  echo "find not found"
  exit 1
fi

echo ""
echo "=== Docker 볼륨 inode (해당 시) ==="
if command -v docker &>/dev/null; then
  docker system df -v 2>/dev/null | head -50 || true
fi

echo ""
echo "참고: /var/lib/docker, /var/lib/containers 등이 상위면 Docker/컨테이너 데이터가 원인입니다."
echo "      Prometheus TSDB 블록 정리 후: RESTART_PROMETHEUS_AFTER_CLEAN=1 ./scripts/prometheus-delete-older-than-14d.sh"
