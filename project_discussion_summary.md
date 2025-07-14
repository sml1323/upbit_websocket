# Upbit WebSocket LLM 프로젝트 논의 요약

## 프로젝트 개요
- **목표**: 기존 Upbit WebSocket → Kafka → PostgreSQL/TimescaleDB → BigQuery 파이프라인에서 BigQuery 부분을 제거하고, TimescaleDB 데이터를 활용한 LLM 기반 프로젝트 구축
- **핵심 고려사항**: LLM 입력 토큰 효율성 최적화

## 현재 시스템 분석
### 기존 아키텍처
```
Upbit WebSocket → Kafka → PostgreSQL(TimescaleDB) → [BigQuery 제거]
```

### 현재 데이터 구조 (제한적)
```sql
trade_data (time, code, trade_price, trade_volume)
```

### 실제 수신 데이터 (풍부함)
Upbit WebSocket에서 다음과 같은 풍부한 데이터가 수신됨:
- 가격 정보: opening_price, high_price, low_price, trade_price, prev_closing_price
- 변동 정보: change, change_price, change_rate
- 거래량 정보: trade_volume, acc_trade_volume, acc_trade_price_24h
- 매수/매도 정보: ask_bid, acc_ask_volume, acc_bid_volume
- 52주 정보: highest_52_week_price, lowest_52_week_price
- 시장 상태: market_state, market_warning

## LLM 프로젝트 아이디어 검토

### 제안된 아이디어들
1. **실시간 시장 분석 리포트 생성기** - 15분/1시간마다 시장 상황 자연어 요약
2. **스마트 알림 시스템** - 급등/급락, 거래량 급증 탐지 및 상황 분석
3. **암호화폐 질의응답 챗봇** - 실시간 데이터 기반 사용자 질문 답변
4. **이상 거래 탐지 및 해석기** - 비정상 패턴 탐지 및 원인 분석

### 토큰 효율성 고려사항
- **문제점**: 52주 데이터 등 대량 데이터를 LLM에 직접 입력하면 토큰 비용 폭증
- **해결책**: 사전 집계 + 요약 지표 방식 채택

## 기술적 접근법 결정

### MCP (Model Context Protocol) 채택
- **선택 이유**: 실시간성과 유연성
- **활용 방안**: FreePeak/db-mcp-server (PostgreSQL/TimescaleDB 지원)

### 토큰 효율적 아키텍처
```
DB 쿼리 → 통계 계산 → 요약 지표 → LLM 분석
```

**토큰 소모량 비교:**
- ❌ 비효율적: 원시 데이터 전달 (~50,000 토큰/시간)
- ✅ 효율적: 계산된 지표만 전달 (~500 토큰)

## 최적화된 TimescaleDB 스키마 설계

### 1. 메인 Ticker 테이블 (실시간 데이터)
```sql
CREATE TABLE ticker_data (
    time TIMESTAMPTZ NOT NULL,
    code TEXT NOT NULL,
    
    -- 가격 정보
    trade_price DECIMAL,
    opening_price DECIMAL,
    high_price DECIMAL,
    low_price DECIMAL,
    prev_closing_price DECIMAL,
    
    -- 변동률 정보 (LLM 해석 최적화)
    change_type TEXT, -- "RISE", "FALL", "EVEN"
    change_price DECIMAL,
    change_rate DECIMAL,
    
    -- 거래량 정보
    trade_volume DECIMAL,
    acc_trade_volume DECIMAL,
    acc_trade_price_24h DECIMAL,
    acc_trade_volume_24h DECIMAL,
    
    -- 매수/매도 정보
    ask_bid TEXT,
    acc_ask_volume DECIMAL,
    acc_bid_volume DECIMAL,
    
    -- 52주 정보 (저항/지지선)
    highest_52_week_price DECIMAL,
    lowest_52_week_price DECIMAL,
    
    -- 시장 상태
    market_state TEXT,
    market_warning TEXT,
    
    PRIMARY KEY (time, code)
);
```

### 2. 집계 테이블들 (MCP 쿼리 최적화)
- **ohlcv_1m**: 1분 OHLCV 데이터
- **market_summary_5m**: 5분마다 전체 시장 요약
- **anomaly_events**: 이상 거래 탐지 결과
- **technical_indicators**: 사전 계산된 기술적 지표

## MCP 최적화 전략
1. **원시 데이터**: ticker_data (모든 정보 보존)
2. **집계 데이터**: OHLCV, 요약 테이블 (빠른 조회)
3. **해석된 데이터**: 이상 탐지, 기술적 지표 (LLM 친화적)

### MCP 쿼리 예시
```sql
-- "지금 주목할 만한 코인은?"
SELECT code, change_rate, trade_volume/avg_volume_24h as volume_ratio
FROM current_market_view 
WHERE volume_ratio > 2.0 OR ABS(change_rate) > 0.05
ORDER BY volume_ratio DESC LIMIT 5;

-- "W 코인 지금 어때?"
SELECT * FROM get_coin_summary('W', '1 hour');
```

## 다음 단계
1. 기존 consumer.py 수정하여 풍부한 데이터 저장
2. TimescaleDB 스키마 구현 및 집계 테이블 생성
3. MCP 서버 설정 및 연동
4. LLM 기반 분석 기능 구현

## 핵심 설계 원칙
- **토큰 효율성**: 원시 데이터 대신 계산된 지표만 LLM에 전달
- **실시간성**: MCP를 통한 실시간 데이터 접근
- **확장성**: TimescaleDB의 time-series 최적화 활용
- **분석 품질**: 풍부한 원본 데이터 보존 및 활용