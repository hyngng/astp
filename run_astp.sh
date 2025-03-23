#!/bin/bash

# ASTP 환경 변수 설정 스크립트
# 실행 전 아래 API 키 정보를 실제 값으로 변경하세요

# API 키 정보 설정
export KIS_ID="<YOUR_KIS_ID>"
export KIS_ACCOUNT="<YOUR_KIS_ACCOUNT>"
export KIS_APP_KEY="<YOUR_KIS_APP_KEY>" 
export KIS_APP_SECRET="<YOUR_KIS_APP_SECRET>"
export KIS_VIRTUAL_APP_KEY="<YOUR_KIS_VIRTUAL_APP_KEY>"
export KIS_VIRTUAL_APP_SECRET="<YOUR_KIS_VIRTUAL_APP_SECRET>"

# 환경 변수 확인
echo "설정된 환경 변수 확인:"
echo "KIS_ID: ${KIS_ID}"
echo "KIS_ACCOUNT: ${KIS_ACCOUNT}"
echo "KIS_APP_KEY: ${KIS_APP_KEY:0:5}*****"
echo "KIS_APP_SECRET: ${KIS_APP_SECRET:0:5}*****"
echo "KIS_VIRTUAL_APP_KEY: ${KIS_VIRTUAL_APP_KEY:0:5}*****"
echo "KIS_VIRTUAL_APP_SECRET: ${KIS_VIRTUAL_APP_SECRET:0:5}*****"

# 실행 디렉토리로 이동
cd "$(dirname "$0")"

# 필요한 패키지 설치 확인 (첫 실행 시)
if [ ! -d "venv" ]; then
    echo "가상 환경을 생성하고 필요한 패키지를 설치합니다..."
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# ASTP 프로그램 실행
echo "ASTP 프로그램을 시작합니다..."
python -m main.main

# 종료 메시지
echo "ASTP 프로그램이 종료되었습니다." 