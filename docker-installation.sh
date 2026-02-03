#!/bin/bash

# 1. 시스템 업데이트 및 필수 패키지 설치
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release

# 2. Docker 공식 GPG 키 추가
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 3. Docker 저장소(Repository) 설정
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 4. Docker 엔진 설치
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 5. 현재 사용자를 docker 그룹에 추가 (권한 부여)
# $USER는 현재 로그인한 사용자 계정을 의미합니다.
sudo usermod -aG docker $USER

# 6. 변경된 그룹 권한을 즉시 적용 (로그아웃 없이 사용 가능하게)
newgrp docker <<EONG
# 7. 설치 확인
docker --version
docker compose version
echo "--------------------------------------------------"
echo "Docker 설치 및 사용자 권한 설정이 완료되었습니다!"
echo "이제 'sudo' 없이 docker 명령어를 사용할 수 있습니다."
EONG
