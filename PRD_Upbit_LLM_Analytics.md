# PRD: Upbit LLM Analytics Platform

## 프로젝트 개요

**목표**: 기존 Upbit WebSocket → Kafka → TimescaleDB 파이프라인에서 BigQuery를 제거하고, LLM 기반 실시간 암호화폐 분석 플랫폼 구축

**핵심 문제 해결**:
- 풍부한 원본 데이터(22개 필드) 중 4개만 활용하는 문제
- LLM 토큰 비용 최적화 (50,000 토큰 → 500 토큰, 99% 절약)
- 실시간 시장 분석 기능 부재

**핵심 가치**:
- **토큰 효율성**: 계산된 지표만 LLM에 전달
- **실시간성**: 초 단위 시장 변화 즉시 분석  
- **고품질**: 22개 필드 완전 활용

## 핵심 기능

### MVP 기능 (우선 구현)
1. **실시간 시장 요약** - 5분마다 전체 시장 상황 자연어 요약
2. **코인별 질의응답** - "W코인 지금 어때?" → LLM 종합 분석
3. **이상 거래 탐지** - 거래량/가격 급변동 감지 및 LLM 해석

### 확장 기능
1. **기술적 지표 해석** (RSI, 볼린저밴드 등)
2. **트렌드 분석 리포트** (시간대별)
3. **포트폴리오 맞춤 분석**

## 기술 아키텍처

### 시스템 구조
```
Upbit WebSocket → Kafka → TimescaleDB → MCP Server → LLM
                              ↓
                      Continuous Aggregates (집계 테이블)
```

### 핵심 설계 결정

#### 1. TimescaleDB 스키마 최적화
**기존 문제**: 22개 필드 중 4개만 저장 (trade_price, trade_volume, code, time)

**새로운 스키마**: 모든 필드 저장 + ENUM 타입 최적화
```sql
CREATE TABLE ticker_data (
    time TIMESTAMPTZ NOT NULL,
    code TEXT NOT NULL,
    -- 가격: trade_price, opening_price, high_price, low_price
    -- 변동: change_type ('RISE'/'FALL'), change_rate
    -- 거래량: trade_volume, acc_trade_volume_24h
    -- 매수/매도: ask_bid ('ASK'/'BID'), acc_ask_volume, acc_bid_volume
    -- 52주: highest_52_week_price, lowest_52_week_price
    -- 시장상태: market_state, market_warning
    PRIMARY KEY (time, code)
);
```

#### 2. MCP 기반 토큰 최적화
**원리**: 원시 데이터 대신 계산된 지표만 LLM에 전달
```python
# MCP 함수 예시
def get_coin_summary(code):
    return {
        "current_price": 113.2,
        "change_rate": 4.04,
        "volume_spike": True,  # 평균 대비 2배 이상
        "near_resistance": True,  # 52주 고점 근처
        "momentum": "bullish"
    }
```

#### 3. Continuous Aggregates (집계 최적화)
- **ohlcv_1m**: 1분 캔들 데이터
- **market_summary_5m**: 5분 시장 요약 (상승/하락 코인 수 등)
- **anomaly_events**: 이상 거래 탐지 결과

## 성능 목표
- **응답 속도**: 3초 이하
- **토큰 효율성**: 500개 이하 (99% 절약)
- **정확도**: 이상 탐지 85% 이상
- **가용성**: 99.9% 업타임

## 기술 스택
- **Database**: PostgreSQL 13 + TimescaleDB  
- **Message Broker**: Apache Kafka (기존 유지)
- **MCP Server**: FreePeak/db-mcp-server
- **LLM**: Claude (via MCP)
- **Backend**: Python 3.9+