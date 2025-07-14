# MCP Server Setup & LLM Integration

## 🎯 목표
Upbit WebSocket 데이터를 MCP를 통해 GPT-4o-mini에게 토큰 효율적으로 제공하여 실시간 암호화폐 분석 수행

## 📂 파일 구조
```
mcp/
├── config.json              # MCP 서버 설정
├── start_mcp_server.sh      # MCP 서버 시작 스크립트
├── test_mcp_functions.py    # MCP 함수 테스트
├── llm_integration_test.py  # GPT-4o-mini 연동 테스트
└── README.md               # 이 파일
```

## 🚀 설치 및 실행

### 1. 사전 준비
```bash
# OpenAI API 키 설정
export OPENAI_API_KEY=your_openai_api_key_here

# 의존성 설치
pip install -r requirements.txt

# 데이터베이스 스키마 배포 (MCP 함수 포함)
python deploy_new_schema.py
```

### 2. MCP 서버 시작
```bash
cd mcp
./start_mcp_server.sh
```

### 3. MCP 함수 테스트
```bash
cd mcp
python test_mcp_functions.py
```

### 4. LLM 연동 테스트
```bash
cd mcp
python llm_integration_test.py
```

## 🔧 핵심 MCP 함수들

### 1. get_coin_summary(code, timeframe)
특정 코인의 현재 상태를 요약
```sql
SELECT * FROM get_coin_summary('KRW-BTC', 1);
```

**출력 예시:**
- current_price: 현재가
- change_rate: 변동률
- trend: 추세 (bullish/bearish/neutral)
- volume_spike: 거래량 급증 여부
- support_level/resistance_level: 지지/저항선
- rsi_signal: RSI 신호
- volatility: 변동성 수준
- market_cap_rank: 시가총액 등급

### 2. get_market_movers(type, limit, timeframe)
시장에서 가장 활발한 코인들 조회
```sql
-- 상위 상승 코인 10개
SELECT * FROM get_market_movers('gainers', 10, 1);

-- 상위 하락 코인 5개  
SELECT * FROM get_market_movers('losers', 5, 1);

-- 거래량 상위 코인들
SELECT * FROM get_market_movers('volume', 10, 1);
```

### 3. detect_anomalies(timeframe, sensitivity)
이상 거래 패턴 탐지
```sql
-- 보통 민감도로 1시간 이상거래 탐지
SELECT * FROM detect_anomalies(1, 3);

-- 높은 민감도로 탐지
SELECT * FROM detect_anomalies(1, 5);
```

**이상 유형:**
- volume_spike: 거래량 급증
- price_volatility: 가격 급변동

### 4. get_market_overview()
전체 시장 개요
```sql
SELECT * FROM get_market_overview();
```

## 🤖 LLM 연동 시나리오

### 시나리오 1: 코인별 분석
```python
analytics = UpbitLLMAnalytics(api_key, mcp_url)
analysis = analytics.analyze_coin("KRW-BTC")
print(analysis)
```

### 시나리오 2: 전체 시장 분석
```python
market_analysis = analytics.market_overview_analysis()
print(market_analysis)
```

### 시나리오 3: 이상 거래 알림
```python
anomaly_alert = analytics.anomaly_alert_analysis()
print(anomaly_alert)
```

## 🎯 토큰 효율성

### Before (Raw Data): ~50,000 토큰
```json
{
  "KRW-BTC": {
    "time": "2025-01-14T10:30:00Z",
    "opening_price": 161740000.0,
    "high_price": 166292000.0,
    "low_price": 161357000.0,
    "trade_price": 166291000.0,
    "prev_closing_price": 161740000.0,
    "acc_trade_price": 229342861607.30978,
    "change": "RISE",
    "change_price": 4551000.0,
    "signed_change_price": 4551000.0,
    "change_rate": 0.0281377519,
    "signed_change_rate": 0.0281377519,
    "ask_bid": "ASK",
    "trade_volume": 0.01234318,
    "acc_trade_volume": 1399.45618806,
    "trade_date": "20250714",
    "trade_time": "054646",
    "trade_timestamp": 1752472006660,
    "acc_ask_volume": 611.90590443,
    "acc_bid_volume": 787.55028363,
    "highest_52_week_price": 166292000.0,
    "highest_52_week_date": "2025-07-14",
    "lowest_52_week_price": 72100000.0,
    "lowest_52_week_date": "2024-08-05",
    "market_state": "ACTIVE",
    "is_trading_suspended": false,
    "delisting_date": null,
    "market_warning": "NONE",
    "timestamp": 1752472006690,
    "acc_trade_price_24h": 381242118431.79364,
    "acc_trade_volume_24h": 2344.92052835,
    "stream_type": "REALTIME"
  }
  // ... 200개 코인 더
}
```

### After (MCP Functions): ~500 토큰
```json
{
  "code": "KRW-BTC",
  "current_price": 166291000.0,
  "change_rate": 2.81,
  "trend": "bullish",
  "volume_spike": false,
  "support_level": 161000000.0,
  "resistance_level": 167000000.0,
  "rsi_signal": "overbought",
  "volatility": "medium",
  "market_cap_rank": "large"
}
```

## 🎉 결과: 99% 토큰 절약!

## 🔧 트러블슈팅

### MCP 서버가 시작되지 않는 경우
```bash
# Docker 상태 확인
docker ps | grep upbit-mcp-server

# 로그 확인
docker logs upbit-mcp-server

# 재시작
docker stop upbit-mcp-server
./start_mcp_server.sh
```

### 데이터베이스 연결 실패
```bash
# PostgreSQL 서비스 확인
sudo systemctl status postgresql

# 데이터베이스 접속 테스트
psql -h localhost -U postgres -d coin

# 함수 존재 확인
\df get_coin_summary
```

### OpenAI API 오류
```bash
# API 키 확인
echo $OPENAI_API_KEY

# API 키 설정
export OPENAI_API_KEY=your_key_here
```

## 📈 성능 모니터링

### MCP 서버 상태
```bash
curl http://localhost:9092/health
```

### 쿼리 성능 확인
```sql
-- 최근 1시간 데이터 건수
SELECT COUNT(*) FROM ticker_data WHERE time >= NOW() - INTERVAL '1 hour';

-- 함수 실행 시간 측정
\timing
SELECT * FROM get_coin_summary('KRW-BTC', 1);
```

## 🚀 다음 단계
1. **Week 3-4**: FastAPI 웹 인터페이스 구축
2. **Week 5**: 실시간 WebSocket 스트리밍
3. **Week 6**: 모니터링 및 알림 시스템
4. **Week 7**: 성능 최적화 및 배포