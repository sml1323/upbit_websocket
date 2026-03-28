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
                                   │ + KakaoTalk│
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
- **Alert**: Telegram Bot + KakaoTalk
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

## KakaoTalk 알림 설정

카카오톡 "나에게 보내기"로 이상 감지 알림을 받을 수 있습니다.

### 1. Kakao Developers 앱 등록

1. [Kakao Developers](https://developers.kakao.com/) 접속 → 로그인
2. **내 애플리케이션** → **애플리케이션 추가하기**
3. 앱 이름 입력 후 생성
4. **앱 키** 탭에서 **REST API 키** 복사

### 2. 카카오 로그인 활성화

1. **제품 설정** → **카카오 로그인** → 활성화 ON
2. **동의항목** → `talk_message` (카카오톡 메시지 전송) 선택 동의
3. **Redirect URI** 등록: `https://localhost:3000/callback` (토큰 발급용)

### 3. 인가 코드 발급 (브라우저)

아래 URL을 브라우저에서 열고, 동의 후 리다이렉트된 URL에서 `code=` 값을 복사:

```
https://kauth.kakao.com/oauth/authorize?client_id={REST_API_KEY}&redirect_uri=https://localhost:3000/callback&response_type=code&scope=talk_message
```

### 4. Access Token 발급

```bash
curl -X POST https://kauth.kakao.com/oauth/token \
  -d "grant_type=authorization_code" \
  -d "client_id={REST_API_KEY}" \
  -d "redirect_uri=https://localhost:3000/callback" \
  -d "code={AUTHORIZATION_CODE}"
```

응답에서 `access_token`과 `refresh_token`을 복사합니다.

### 5. 환경변수 설정

`.env` 파일에 추가:

```env
KAKAO_REST_API_KEY=your_rest_api_key
KAKAO_ACCESS_TOKEN=your_access_token
KAKAO_REFRESH_TOKEN=your_refresh_token
```

- `access_token`은 6시간 후 만료되지만, 시스템이 자동으로 `refresh_token`으로 갱신합니다.
- `refresh_token`은 2개월 유효. 만료 시 위 과정을 다시 수행합니다.
- severity가 medium 이상인 이상 징후만 카카오톡으로 전송됩니다 (일일 전송 제한 대응).
