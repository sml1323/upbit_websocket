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
├── detector/           # 이상 감지 (Phase 2)
├── agent/              # LangGraph Agent (Phase 3)
├── api/                # FastAPI endpoints (Phase 4)
└── alerts/             # Telegram 알림 (Phase 4)
```

## Tech Stack

- **Streaming**: Upbit WebSocket → Kafka (KRaft mode, bitnami)
- **Storage**: TimescaleDB (hypertable + continuous aggregates)
- **Agent**: LangGraph + LLM (planned)
- **Alert**: Telegram Bot (planned)
- **Infra**: Docker Compose

## Testing

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

## Development Roadmap

- [x] **Phase 1**: Pipeline 정상화 + Docker 통합
- [ ] **Phase 2**: Continuous aggregates + z-score 이상 감지
- [ ] **Phase 3**: LangGraph Agent (3 tools)
- [ ] **Phase 4**: Telegram 알림 + Replay mode + FastAPI
