#!/bin/bash

set -e

echo "🚀 Upbit LLM Analytics 서비스 시작"
echo "=================================="

# 환경 변수 확인
if [ ! -f .env ]; then
    echo "❌ .env 파일이 없습니다. 환경 변수를 설정해주세요."
    exit 1
fi

# Docker Compose 실행
echo "📦 Docker 컨테이너 시작 중..."
docker compose down --remove-orphans 2>/dev/null || true
docker compose up -d

# 서비스 헬스체크
echo ""
echo "🔍 서비스 상태 확인 중..."
sleep 10

# TimescaleDB 헬스체크
echo "  - TimescaleDB 확인 중..."
for i in {1..30}; do
    if docker exec timescaledb pg_isready -U upbit_user -d upbit_analytics >/dev/null 2>&1; then
        echo "    ✅ TimescaleDB 준비 완료"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "    ❌ TimescaleDB 시작 실패"
        exit 1
    fi
    sleep 2
done

# Kafka 헬스체크
echo "  - Kafka 확인 중..."
for i in {1..30}; do
    if docker exec kafka kafka-topics.sh --list --bootstrap-server localhost:9092 >/dev/null 2>&1; then
        echo "    ✅ Kafka 준비 완료"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "    ❌ Kafka 시작 실패"
        exit 1
    fi
    sleep 2
done

# DB 초기 설정
echo ""
echo "🔧 데이터베이스 초기 설정 중..."

# 필요한 함수들이 있는지 확인하고 없으면 생성
docker exec timescaledb psql -U upbit_user -d upbit_analytics -c "
SELECT 1 FROM pg_proc WHERE proname = 'get_coin_summary';
" | grep -q "1 row" || {
    echo "  - MCP 함수 생성 중..."
    docker exec timescaledb psql -U upbit_user -d upbit_analytics -f /docker-entrypoint-initdb.d/mcp_functions.sql
}

# 샘플 데이터 확인 및 생성
DATA_COUNT=$(docker exec timescaledb psql -U upbit_user -d upbit_analytics -t -c "SELECT COUNT(*) FROM ticker_data;")
if [ "$DATA_COUNT" -lt 5 ]; then
    echo "  - 샘플 데이터 생성 중..."
    docker exec timescaledb psql -U upbit_user -d upbit_analytics -c "
    INSERT INTO ticker_data (
        time, code, type, opening_price, high_price, low_price, trade_price, 
        prev_closing_price, change, change_price, signed_change_price, 
        change_rate, signed_change_rate, trade_volume, acc_trade_volume, 
        acc_trade_price, ask_bid, acc_ask_volume, acc_bid_volume, 
        acc_trade_price_24h, acc_trade_volume_24h, highest_52_week_price, 
        highest_52_week_date, lowest_52_week_price, lowest_52_week_date, 
        trade_date, trade_time, trade_timestamp, timestamp, stream_type
    ) VALUES 
    ('2025-07-15 00:00:00', 'KRW-BTC', 'ticker', 95000000, 96000000, 94000000, 95500000, 94500000, 'RISE', 1000000, 1000000, 1.06, 1.06, 0.01, 100, 9550000000, 'ASK', 50, 50, 9550000000, 1000000000, 100000000, '2025-01-01', 90000000, '2025-01-01', '20250715', '000000', 1642204800000, 1642204800000, 'REALTIME'),
    ('2025-07-15 00:05:00', 'KRW-ETH', 'ticker', 3500000, 3600000, 3400000, 3550000, 3450000, 'RISE', 100000, 100000, 2.90, 2.90, 0.5, 500, 1775000000, 'BID', 250, 250, 1775000000, 500000000, 4000000, '2025-01-01', 3000000, '2025-01-01', '20250715', '000500', 1642205100000, 1642205100000, 'REALTIME'),
    ('2025-07-15 00:10:00', 'KRW-XRP', 'ticker', 650, 670, 640, 660, 630, 'RISE', 30, 30, 4.76, 4.76, 1000, 10000, 6600000, 'ASK', 5000, 5000, 6600000, 10000000, 800, '2025-01-01', 500, '2025-01-01', '20250715', '001000', 1642205400000, 1642205400000, 'REALTIME')
    ON CONFLICT (time, code) DO NOTHING;
    "
fi

echo ""
echo "🎯 서비스 접속 정보:"
echo "  - TimescaleDB: localhost:5432 (upbit_user/upbit_password)"
echo "  - Kafka: localhost:9092"
echo "  - MCP Server: localhost:9093"
echo "  - Redis: localhost:6379"
echo ""
echo "🚀 서비스 시작 완료!"
echo ""
echo "다음 명령어로 개별 서비스를 실행하세요:"
echo "  python upbit-kafka/producer.py   # Upbit 데이터 수집"
echo "  python upbit-kafka/consumer.py   # 데이터 저장"
echo "  python realtime_market_summary.py # 실시간 시장 요약"
echo "  python coin_qa_system.py         # 코인 질의응답"
echo ""
echo "웹 클라이언트: market_summary_client.html"