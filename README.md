# Market Incident Copilot

Upbit 실시간 시세 데이터 파이프라인 + AI Agent 기반 이상 감지 시스템

## Architecture

```
Upbit WebSocket (ticker)
       │
       ▼
┌─────────────┐     ┌──────────┐     ┌──────────────┐
│  Producer    │────▶│  Kafka   │────▶│  Consumer    │
│  (container) │     │ (KRaft)  │     │  (container) │
└─────────────┘     └──────────┘     └──────┬───────┘
                                            │ batch INSERT
                                            ▼
                                    ┌──────────────┐
                                    │ TimescaleDB   │
                                    │  - tickers    │  (hypertable)
                                    │  - agg_1min   │  (continuous aggregate)
                                    │  - agg_5min   │  (continuous aggregate)
                                    │  - incidents  │  (agent reports)
                                    └──────┬───────┘
                                           │
                          ┌────────────────┼────────────────┐
                          ▼                ▼                ▼
                   ┌────────────┐   ┌──────────┐   ┌──────────┐
                   │ Anomaly    │   │ LangGraph │   │ FastAPI  │
                   │ Detector   │──▶│ Agent     │   │ API      │
                   └────────────┘   └────┬─────┘   └──────────┘
                                         │
                                         ▼
                                   ┌──────────┐
                                   │ Telegram  │
                                   │ Alert     │
                                   └──────────┘
```

## Quick Start

```bash
# 1. 환경변수 설정
cp .env.example .env

# 2. 전체 인프라 기동
docker compose up -d

# 3. 데이터 확인
docker compose exec timescaledb psql -U postgres -d upbit -c "SELECT count(*) FROM tickers;"
```

## Project Structure

```
src/
├── config.py           # 공통 설정 (env, logging, DB, Kafka)
├── pipeline/
│   ├── producer.py     # Upbit WebSocket → Kafka
│   └── consumer.py     # Kafka → TimescaleDB (batch INSERT)
├── detector/
│   └── anomaly.py     # z-score 이상 감지 (24h rolling window)
├── agent/
│   ├── graph.py       # LangGraph 워크플로우
│   └── tools/         # query_market, search_news, write_report
├── api/
│   └── main.py        # FastAPI (incidents CRUD + replay)
├── alerts/
│   └── telegram.py    # Telegram Bot 알림
└── scheduler.py       # APScheduler (5분 polling)
```

## Tech Stack

- **Streaming**: Upbit WebSocket → Kafka (KRaft mode, bitnami)
- **Storage**: TimescaleDB (hypertable + continuous aggregates)
- **Agent**: LangGraph + GPT-4o-mini
- **Alert**: Telegram Bot
- **API**: FastAPI (incidents + replay)
- **Infra**: Docker Compose

## Testing

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

## Development Roadmap

- [x] **Phase 1**: Pipeline 정상화 + Docker 통합
- [x] **Phase 2**: Continuous aggregates + z-score 이상 감지
- [x] **Phase 3**: LangGraph Agent (3 tools)
- [x] **Phase 4**: Telegram 알림 + Replay mode + FastAPI

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/incidents` | 최근 incident 목록 (?source=live/replay) |
| GET | `/incidents/{id}` | Incident 상세 조회 |
| POST | `/replay` | 과거 시점 이상 감지 재실행 |

```bash
# API 서버 실행
uvicorn src.api.main:app --reload

# Scheduler 실행 (5분마다 이상 감지)
python3 -m src.scheduler
```
