#!/bin/bash
# 전체 시스템 디스크 최적화 (Prometheus/Loki/Grafana 볼륨은 건드리지 않음)
# 사용법: ./scripts/disk-free-now.sh
# 실제 정리 실행: YES=1 ./scripts/disk-free-now.sh
set -e
YES="${YES:-0}"
JOURNAL_DAYS="${JOURNAL_DAYS:-7}"
JOURNAL_MAX_SIZE="${JOURNAL_MAX_SIZE:-100M}"

echo "=== 현재 디스크 사용량 ==="
df -h / /var /var/lib/docker 2>/dev/null || df -h /
echo ""

do_docker_prune() {
  if [ "$YES" = "1" ]; then
    docker system prune -af
    docker builder prune -af
    echo "  [완료] Docker 이미지/빌드캐시 정리"
  else
    echo "  docker system prune -af && docker builder prune -af"
  fi
}

do_journal_vacuum() {
  if [ "$YES" = "1" ]; then
    sudo journalctl --vacuum-time="${JOURNAL_DAYS}d"
    sudo journalctl --vacuum-size="$JOURNAL_MAX_SIZE"
    echo "  [완료] journal 로그 ${JOURNAL_DAYS}일 + ${JOURNAL_MAX_SIZE} 이하로 축소"
  else
    echo "  sudo journalctl --vacuum-time=${JOURNAL_DAYS}d"
    echo "  sudo journalctl --vacuum-size=$JOURNAL_MAX_SIZE"
  fi
}

do_apt_clean() {
  if [ "$YES" = "1" ]; then
    sudo apt-get clean
    sudo apt-get autoremove -y
    echo "  [완료] apt 캐시 및 미사용 패키지 제거"
  else
    echo "  sudo apt-get clean && sudo apt-get autoremove -y"
  fi
}

do_snap_clean() {
  if ! command -v snap >/dev/null 2>&1; then
    return 0
  fi
  if [ "$YES" = "1" ]; then
    old=$(snap list --all | awk '/disabled/{print $1, $3}')
    if [ -n "$old" ]; then
      echo "$old" | while read -r name rev; do
        sudo snap remove "$name" --revision="$rev"
      done
      echo "  [완료] Snap 미사용 리비전 제거"
    else
      echo "  [건너뜀] 제거할 Snap 리비전 없음"
    fi
  else
    echo "  sudo snap list --all  # disabled 리비전 확인 후 수동 제거"
  fi
}

do_tmp_clean() {
  if [ "$YES" = "1" ]; then
    # 시스템 /tmp 내 오래된 임시파일만 (runc 등), 전체 삭제는 위험하므로 건드리지 않음
    if [ -d /var/lib/docker/tmp ]; then
      sudo rm -rf /var/lib/docker/tmp/*
      echo "  [완료] Docker tmp 정리"
    fi
    # 사용자 터미널 tmp 정리는 제외 (실수 방지)
  else
    echo "  /var/lib/docker/tmp 비우기: sudo rm -rf /var/lib/docker/tmp/*  (필요 시)"
  fi
}

echo "=== 1. Docker 정리 (monitoring 볼륨 유지) ==="
do_docker_prune
echo ""

echo "=== 2. systemd journal 로그 축소 ==="
do_journal_vacuum
echo ""

echo "=== 3. APT 캐시 및 미사용 패키지 ==="
do_apt_clean
echo ""

echo "=== 4. Snap 미사용 리비전 ==="
do_snap_clean
echo ""

echo "=== 5. Docker 내부 tmp (선택) ==="
do_tmp_clean
echo ""

if [ "$YES" != "1" ]; then
  echo "--- 실제로 위 정리를 실행하려면: YES=1 $0 ---"
  echo "  journal 기간/용량: JOURNAL_DAYS=3 JOURNAL_MAX_SIZE=50M YES=1 $0"
  echo ""
fi

echo "=== 디스크 사용량 점검 명령 ==="
echo "  볼륨 폴더 전체:     sudo du -sh /var/lib/docker/volumes/"
echo "  볼륨별:             for d in /var/lib/docker/volumes/*/; do [ -d \"\$d\" ] && sudo du -sh \"\$d\"; done"
echo "  큰 디렉터리 찾기:   sudo du -hx / 2>/dev/null | sort -hr | head -20"
echo ""

if [ "$YES" = "1" ]; then
  echo "=== 정리 후 디스크 사용량 ==="
  df -h / /var /var/lib/docker 2>/dev/null || df -h /
  echo "Prometheus/Loki/Grafana 데이터는 삭제하지 않았습니다."
fi
