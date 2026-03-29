# Coin Anomaly Agent

Upbit 실시간 시세 데이터를 수집하고, 4개 지표 앙상블로 이상을 감지하고, Multi-Agent AI가 분석 리포트를 작성하는 시스템.

`docker compose up` 한 번이면 데이터 수집부터 이상 감지, AI 분석, KakaoTalk 알림까지 전부 자동으로 동작합니다.

![Grafana Dashboard](docs/images/grafana-dashboard.png)

## Features

| | Feature | Description |
|---|---------|-------------|
| **Pipeline** | 실시간 데이터 수집 | Upbit WebSocket -> Kafka -> TimescaleDB |
| **Detection** | 앙상블 이상 감지 | Z-Score, Bollinger Bands, RSI, VWAP 4개 지표 가중치 투표 |
| **AI** | Multi-Agent 분석 | Market Agent + News Agent 병렬 -> Report Agent 종합 (LangGraph DAG) |
| **Alert** | 멀티 채널 알림 | Telegram + KakaoTalk 동시 지원 |
| **Dashboard** | Grafana 모니터링 | 거래대금 Top 10, 실시간 가격, Z-Score, Incidents |
| **Report** | 리포트 뷰어 | 각 Agent별 응답을 구조화된 HTML로 조회 |
| **API** | REST API | FastAPI 기반 incidents CRUD + Replay mode |

## Screenshots

<table>
<tr>
<td width="50%">

**리포트 목록** (`localhost:8000/reports`)

![Report List](docs/images/report-list.png)

</td>
<td width="50%">

**리포트 상세** (Agent별 분석 결과)

![Report Detail](docs/images/report-detail.png)

</td>
</tr>
<tr>
<td width="50%">

**Grafana 대시보드** (`localhost:3001`)

![Grafana](docs/images/grafana-dashboard.png)

</td>
<td width="50%">

**KakaoTalk 알림**

![KakaoTalk Alert](docs/images/kakao-alert.png)

</td>
</tr>
</table>

## Architecture

```
Upbit WebSocket
       |
       v
  [ Producer ] ----> [ Kafka ] ----> [ Consumer ]
                     (KRaft)              |
                                     batch INSERT
                                          v
                                   [ TimescaleDB ]
                                          |
                    +---------------------+---------------------+
                    |                     |                     |
            [ Ensemble Detector ]   [ FastAPI ]          [ Grafana ]
            (Z-Score + BB + RSI     /reports             :3001
             + VWAP)                /incidents
                    |
                    v (이상 감지 시)
            +------------------+
            | Multi-Agent DAG  |
            |                  |
            | Market   News   |  <- 병렬 실행
            | Agent    Agent  |
            |       \  /       |
            |    Report Agent  |  <- fan-in 종합
            +--------+---------+
                     |
              +------+------+
              |             |
         [ Telegram ]  [ KakaoTalk ]
```

### Multi-Agent System

LangGraph 기반 Supervisor + Sub-Agent DAG:

- **Market Agent**: TimescaleDB에서 OHLCV 데이터 조회, LLM으로 기술적 분석
- **News Agent**: SerpAPI/CryptoPanic 뉴스 검색, LLM으로 연관성 분석
- **Report Agent**: 시장분석 + 뉴스분석 종합, 최종 리포트 작성 + 신뢰도 점수

Market Agent와 News Agent가 **병렬 실행**되고, Report Agent가 fan-in으로 종합합니다.

### Ensemble Anomaly Detection

단일 Z-Score 대신 4개 지표의 앙상블 투표 시스템. IndicatorBase ABC + Registry 패턴으로 새 지표 추가 시 기존 코드 수정 0.

| Indicator | Method | Weight | Anomaly Condition |
|-----------|--------|--------|-------------------|
| Z-Score | 24h rolling mean/std | 0.30 | \|z\| >= 3.0 |
| Bollinger Bands | MA(60) +/- 2 sigma | 0.25 | %B > 1.0 or < 0.0 |
| RSI | 60-period gain/loss | 0.20 | RSI > 75 or < 25 |
| VWAP | volume-weighted avg | 0.25 | deviation > 2% |

가중치 합 >= 0.5 이면 이상 판정. 동시 발화 수로 severity 결정 (1=low, 2=medium, 3=high, 4=critical).

## Quick Start

```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일에 OPENAI_API_KEY 입력 (필수), 나머지는 선택

# 2. 전체 시스템 기동
docker compose up -d

# 3. 확인
open http://localhost:3001   # Grafana (admin/admin)
open http://localhost:8000/reports  # 리포트 뷰어
```

> [!NOTE]
> `docker compose up` 한 번이면 Kafka, TimescaleDB, Producer, Consumer, Scheduler, API, Grafana 전부 기동됩니다.
> Scheduler가 5분마다 자동으로 이상 감지 -> AI 분석 -> 알림을 수행합니다.

## Project Structure

```
src/
├── config.py              # 환경변수, 로깅, DB 설정
├── pipeline/
│   ├── producer.py        # Upbit WebSocket -> Kafka
│   └── consumer.py        # Kafka -> TimescaleDB (batch INSERT)
├── detector/
│   ├── base.py            # IndicatorBase ABC + Registry
│   ├── zscore.py          # Z-Score 지표
│   ├── bollinger.py       # Bollinger Bands 지표
│   ├── rsi.py             # RSI 지표
│   ├── vwap.py            # VWAP 지표
│   └── ensemble.py        # EnsembleScorer + batch scoring
├── agent/
│   ├── graph.py           # Supervisor DAG (fan-out/fan-in)
│   ├── market_agent.py    # Market Analyst Agent
│   ├── news_agent.py      # News Analyst Agent
│   ├── report_agent.py    # Report Writer Agent
│   └── tools/             # query_market, search_news, write_report
├── api/
│   └── main.py            # FastAPI + HTML 리포트 뷰어
├── alerts/
│   ├── telegram.py        # Telegram Bot 알림
│   └── kakao.py           # KakaoTalk 나에게 보내기
└── scheduler.py           # APScheduler (5분 polling)
```

## Tech Stack

| Category | Technology |
|----------|-----------|
| Streaming | Upbit WebSocket, Kafka (KRaft) |
| Storage | TimescaleDB (hypertable + continuous aggregates) |
| Detection | 4-indicator ensemble (Z-Score, BB, RSI, VWAP) |
| AI Agent | LangGraph Multi-Agent DAG, GPT-4o-mini |
| Alert | Telegram Bot, KakaoTalk |
| API | FastAPI |
| Dashboard | Grafana |
| Infra | Docker Compose |
| Test | pytest (108 tests) |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/reports` | 리포트 목록 (HTML) |
| GET | `/reports/{id}` | 리포트 상세 - Agent별 분석 (HTML) |
| GET | `/incidents` | Incident 목록 (JSON) |
| GET | `/incidents/{id}` | Incident 상세 (JSON) |
| POST | `/replay` | 과거 시점 이상 감지 재실행 |
| GET | `/docs` | Swagger UI |

## Testing

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
# 108 passed
```

## Environment Variables

`cp .env.example .env` 후 필요한 값을 입력하세요.

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | GPT-4o-mini API 키 (Agent 분석용) |
| `SERPAPI_API_KEY` | No | 뉴스 검색 API (월 100회 무료) |
| `CRYPTOPANIC_API_KEY` | No | 크립토 뉴스 API (무료 tier) |
| `TELEGRAM_BOT_TOKEN` | No | Telegram 봇 토큰 |
| `TELEGRAM_CHAT_ID` | No | Telegram 채팅 ID |
| `KAKAO_REST_API_KEY` | No | Kakao Developers REST API 키 |
| `KAKAO_ACCESS_TOKEN` | No | Kakao OAuth access token |
| `KAKAO_REFRESH_TOKEN` | No | Kakao OAuth refresh token |

## KakaoTalk 알림 설정

카카오톡 "나에게 보내기"로 이상 감지 알림을 받을 수 있습니다 (severity medium 이상).

### 1. Kakao Developers 앱 등록

[Kakao Developers](https://developers.kakao.com/) 접속 -> 앱 생성 -> REST API 키 복사

### 2. 카카오 로그인 설정

- **카카오 로그인** 활성화 ON
- **동의항목** -> `talk_message` 선택 동의
- **Redirect URI**: `https://localhost:3000/callback`

### 3. 토큰 발급

**Step 1)** 브라우저에서 아래 URL을 열고 카카오 로그인 + 동의:

```
https://kauth.kakao.com/oauth/authorize?client_id={REST_API_KEY}&redirect_uri=https://localhost:3000/callback&response_type=code&scope=talk_message
```

**Step 2)** "사이트에 연결할 수 없음" 페이지가 뜨면 정상. **URL 바**에서 `code=` 뒤의 값을 복사:

```
https://localhost:3000/callback?code=여기가_인가코드
```

**Step 3)** 터미널에서 토큰 발급:

```bash
curl -X POST https://kauth.kakao.com/oauth/token \
  -d "grant_type=authorization_code" \
  -d "client_id={REST_API_KEY}" \
  -d "redirect_uri=https://localhost:3000/callback" \
  -d "code={위에서_복사한_인가코드}"
```

**Step 4)** 응답 JSON에서 `access_token`과 `refresh_token`을 복사하여 `.env`에 입력:

```env
KAKAO_REST_API_KEY=your_key
KAKAO_ACCESS_TOKEN=응답의_access_token_값
KAKAO_REFRESH_TOKEN=응답의_refresh_token_값
```

> [!TIP]
> `access_token`은 6시간마다 만료되지만, 시스템이 `refresh_token`으로 자동 갱신합니다.
> `refresh_token`은 2개월 유효. 만료 시 Step 1부터 다시 수행합니다.
