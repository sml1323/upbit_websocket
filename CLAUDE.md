# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Upbit LLM Analytics Platform - 실시간 암호화폐 분석 플랫폼 구축 프로젝트입니다. Upbit WebSocket API에서 22개 필드의 완전한 데이터를 수집하고, MCP 서버를 통해 LLM에게 토큰 효율적으로(99% 절약) 전달하여 실시간 시장 분석을 제공합니다.

## Architecture

현재 데이터 플로우:
```
Upbit WebSocket → Kafka → TimescaleDB → MCP Server → LLM
                              ↓
                      Continuous Aggregates (집계 테이블)
```

## Key Components

### 1. Data Collection (`upbit-kafka/`)
- **producer.py**: Upbit WebSocket API에서 22개 필드 완전 수집 및 Kafka 전송
- **consumer.py**: Kafka에서 데이터 소비하여 TimescaleDB에 저장 (22필드 처리)
- Uses confluent-kafka for message broker operations

### 2. Message Broker
- Kafka runs in Docker containers via docker-compose.yml
- Topic: `upbit_ticker` (configurable via .env)
- Zookeeper for cluster coordination

### 3. Data Storage
- PostgreSQL with TimescaleDB extension for time-series optimization
- Main table: `ticker_data` with 22 fields including all price, volume, and market data
- Continuous Aggregates: ohlcv_1m, market_summary_5m, volume_anomalies_1h

### 4. LLM Integration (`mcp-server/`)
- **FreePeak/db-mcp-server**: MCP 서버로 TimescaleDB와 LLM 연동
- **핵심 MCP 함수**: get_coin_summary, get_market_movers, detect_anomalies
- 토큰 효율성: 50,000 토큰 → 500 토큰 (99% 절약)

### 5. MVP Services (`mvp-services/`)
- **realtime_market_summary.py**: 실시간 시장 요약 (포트 8765, WebSocket)
- **coin_qa_system.py**: 코인 Q&A 시스템 (포트 8080, OpenAI 연동)
- **anomaly_detection_system.py**: 이상 탐지 시스템 (5분 주기 모니터링)

## Development Commands

### Environment Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Deploy TimescaleDB schema (22 fields + MCP functions)
python deploy_new_schema.py
```

### Infrastructure
```bash
# Start all services (통합 docker-compose.yml)
docker-compose up -d

# Individual service start
docker-compose up -d timescaledb    # TimescaleDB 
docker-compose up -d kafka         # Kafka + Zookeeper
docker-compose up -d mcp-server    # MCP Server
```

### Data Pipeline
```bash
# Start data producer (22-field Upbit WebSocket)
cd upbit-kafka
python producer.py

# Start data consumer (saves to TimescaleDB)
cd upbit-kafka
python consumer.py

# Test MCP functions
python test_mcp_connection.py
```

### MVP Services
```bash
# Start all MVP services
docker-compose up -d mvp-market-summary mvp-coin-qa mvp-anomaly-detection

# Individual MVP service start
docker-compose up -d mvp-market-summary    # 실시간 시장 요약
docker-compose up -d mvp-coin-qa          # 코인 Q&A 시스템  
docker-compose up -d mvp-anomaly-detection # 이상 탐지 시스템
```

### Services Access
- TimescaleDB: localhost:5432 (upbit_user/upbit_password)
- Kafka: localhost:9092
- MCP Server: localhost:9093
- Redis Cache: localhost:6379
- MVP Market Summary: localhost:8765 (WebSocket)
- MVP Coin Q&A: localhost:8080 (HTTP)
- MVP Anomaly Detection: Background service

## Environment Variables

Configure via .env file:
- `KAFKA_SERVERS`: Kafka bootstrap servers (default: localhost:9092)
- `KAFKA_TOPIC`: Topic name (default: upbit_ticker)
- `KAFKA_GROUP_ID`: Consumer group (default: default_group)
- `TIMESCALEDB_*`: Database connection parameters
- `OPENAI_API_KEY`: OpenAI API key for MVP services

## Data Schema

PostgreSQL/TimescaleDB `ticker_data` table (22 fields):
- **가격 데이터**: trade_price, opening_price, high_price, low_price, prev_closing_price
- **변동 데이터**: change_type, change_price, change_rate, signed_change_price, signed_change_rate
- **거래량**: trade_volume, acc_trade_volume, acc_trade_price, acc_trade_volume_24h, acc_trade_price_24h
- **매수/매도**: ask_bid, acc_ask_volume, acc_bid_volume
- **52주 데이터**: highest_52_week_price, highest_52_week_date, lowest_52_week_price, lowest_52_week_date
- **시장 상태**: market_state, is_trading_suspended, market_warning

## Docker Images

The project uses:
- `timescale/timescaledb:2.14.2-pg13` for time-series database
- `wurstmeister/kafka:latest` and `wurstmeister/zookeeper:latest` for message broker
- `freepeak/db-mcp-server` for LLM integration via MCP
- `redis:7-alpine` for caching
- `python:3.9-slim` for MVP services (custom built images)

## Important Notes

- 22개 필드 완전 수집으로 기존 4개 필드 대비 데이터 품질 대폭 향상
- KafkaProducerClient handles WebSocket reconnection automatically
- MCP functions provide 99% token efficiency (50K→500 tokens)
- TimescaleDB Continuous Aggregates for real-time analytics
- No BigQuery or Airflow - focus on real-time LLM integration

## MVP Implementation Status (2025-07-15)

### ✅ Completed Features
1. **실시간 시장 요약 서비스** (`mvp-market-summary`)
   - 5분 주기 시장 분석 및 WebSocket 브로드캐스트
   - HTML 클라이언트 포함 (market_summary_client.html)
   - 포트 8765에서 WebSocket 서버 실행

2. **코인 Q&A 시스템** (`mvp-coin-qa`)
   - 자연어 질의 처리 ("BTC 어때?", "비트코인 분석해줘")
   - OpenAI GPT-4o-mini 연동 완료
   - 토큰 효율적 프롬프트 최적화
   - Docker 환경에서 자동 테스트 모드 실행

3. **이상 탐지 시스템** (`mvp-anomaly-detection`)
   - 거래량/가격 급변 탐지 (통계적 분석)
   - 5분 주기 모니터링
   - DB 함수 `detect_anomalies()` 연동
   - 실시간 알림 시스템

### 🔧 해결된 기술 이슈
- Docker EOF 에러: `input()` 함수 → 자동 테스트 모드 변경
- OpenAI API 호환성: v0.28 → v1.56.2 업그레이드
- DB 함수 매개변수 오류: `detect_anomalies(timeframe_hours, sensitivity)` 수정
- Kafka 네트워크 연결: Docker Compose 네트워크 설정 최적화

### 📊 현재 운영 상태
- **전체 컨테이너**: 10개 서비스 정상 실행
- **데이터 수집**: Upbit WebSocket → Kafka → TimescaleDB 파이프라인 활성
- **LLM 연동**: MCP Server + OpenAI API 완전 연동
- **실시간 분석**: 3개 MVP 서비스 동시 운영
- **데이터 현황**: 244,239건 레코드, 177개 코인 실시간 수집 중

### 🔌 VSCode DB 연결 (WSL 환경)
WSL에서 실행 중이므로 VSCode DB 확장 연결 시 다음 설정 사용:
```
Host: 172.31.65.200 (WSL IP - localhost 대신 사용)
Port: 5432
Database: upbit_analytics
Username: upbit_user
Password: upbit_password
SSL Mode: prefer
```