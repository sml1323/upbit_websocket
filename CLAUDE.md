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

### Services Access
- TimescaleDB: localhost:5432 (upbit_user/upbit_password)
- Kafka: localhost:9092
- MCP Server: localhost:9093
- Redis Cache: localhost:6379

## Environment Variables

Configure via .env file:
- `KAFKA_SERVERS`: Kafka bootstrap servers (default: localhost:9092)
- `KAFKA_TOPIC`: Topic name (default: upbit_ticker)
- `KAFKA_GROUP_ID`: Consumer group (default: default_group)
- `TIMESCALEDB_*`: Database connection parameters

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

## Important Notes

- 22개 필드 완전 수집으로 기존 4개 필드 대비 데이터 품질 대폭 향상
- KafkaProducerClient handles WebSocket reconnection automatically
- MCP functions provide 99% token efficiency (50K→500 tokens)
- TimescaleDB Continuous Aggregates for real-time analytics
- No BigQuery or Airflow - focus on real-time LLM integration