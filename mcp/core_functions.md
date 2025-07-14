# Upbit LLM Analytics - 핵심 MCP 함수 설계

## 🎯 목표: 토큰 효율성 99% 절약 (50K → 500 토큰)

---

## 📊 Function 1: get_coin_summary

### 목적
특정 코인의 현재 상태를 요약하여 LLM에게 제공

### 입력 파라미터
- `code`: 코인 코드 (예: "KRW-BTC")
- `timeframe`: 분석 기간 (기본값: "1h")

### 출력 (토큰 최적화)
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

### SQL 쿼리 로직
```sql
WITH latest_data AS (
  SELECT DISTINCT ON (code)
    code, trade_price, change_rate, trade_volume,
    highest_52_week_price, lowest_52_week_price,
    acc_trade_volume_24h
  FROM ticker_data 
  WHERE code = $1 AND time >= NOW() - INTERVAL '1 hour'
  ORDER BY code, time DESC
),
volume_analysis AS (
  SELECT 
    AVG(trade_volume) as avg_volume,
    STDDEV(trade_volume) as volume_stddev
  FROM ticker_data 
  WHERE code = $1 AND time >= NOW() - INTERVAL '24 hours'
)
SELECT 
  l.code,
  l.trade_price as current_price,
  l.change_rate,
  CASE 
    WHEN l.change_rate > 3 THEN 'bullish'
    WHEN l.change_rate < -3 THEN 'bearish' 
    ELSE 'neutral'
  END as trend,
  l.trade_volume > (v.avg_volume + 2 * v.volume_stddev) as volume_spike,
  l.lowest_52_week_price * 1.02 as support_level,
  l.highest_52_week_price * 0.98 as resistance_level,
  CASE 
    WHEN l.change_rate > 5 THEN 'overbought'
    WHEN l.change_rate < -5 THEN 'oversold'
    ELSE 'neutral'
  END as rsi_signal,
  CASE 
    WHEN ABS(l.change_rate) > 10 THEN 'high'
    WHEN ABS(l.change_rate) > 3 THEN 'medium'
    ELSE 'low'
  END as volatility,
  CASE 
    WHEN l.acc_trade_volume_24h > 1000000000 THEN 'large'
    WHEN l.acc_trade_volume_24h > 100000000 THEN 'medium'
    ELSE 'small'
  END as market_cap_rank
FROM latest_data l
CROSS JOIN volume_analysis v;
```

---

## 🔥 Function 2: get_market_movers

### 목적
시장에서 가장 활발하게 움직이는 코인들 상위 10개 제공

### 입력 파라미터
- `timeframe`: 분석 기간 (기본값: "1h") 
- `limit`: 반환할 코인 수 (기본값: 10)
- `type`: "gainers" | "losers" | "volume" (기본값: "gainers")

### 출력 (토큰 최적화)
```json
{
  "type": "gainers",
  "timeframe": "1h", 
  "data": [
    {
      "code": "KRW-W",
      "price": 113.2,
      "change_rate": 4.04,
      "volume_change": 150.5,
      "momentum": "strong"
    },
    // ... 최대 10개
  ],
  "market_summary": {
    "total_rising": 45,
    "total_falling": 32,
    "market_sentiment": "bullish"
  }
}
```

### SQL 쿼리 로직
```sql
WITH current_data AS (
  SELECT DISTINCT ON (code)
    code, trade_price, change_rate, acc_trade_volume_24h,
    time
  FROM ticker_data 
  WHERE time >= NOW() - INTERVAL '1 hour'
  ORDER BY code, time DESC
),
volume_comparison AS (
  SELECT 
    code,
    AVG(acc_trade_volume_24h) as avg_volume_24h
  FROM ticker_data 
  WHERE time >= NOW() - INTERVAL '7 days'
  GROUP BY code
),
market_stats AS (
  SELECT 
    COUNT(*) FILTER (WHERE change_rate > 0) as rising_count,
    COUNT(*) FILTER (WHERE change_rate < 0) as falling_count,
    COUNT(*) as total_count
  FROM current_data
)
SELECT 
  c.code,
  c.trade_price as price,
  c.change_rate,
  (c.acc_trade_volume_24h / NULLIF(v.avg_volume_24h, 0)) * 100 as volume_change,
  CASE 
    WHEN c.change_rate > 10 THEN 'very_strong'
    WHEN c.change_rate > 5 THEN 'strong'
    WHEN c.change_rate > 1 THEN 'moderate'
    ELSE 'weak'
  END as momentum,
  -- Market summary
  m.rising_count,
  m.falling_count,
  CASE 
    WHEN m.rising_count::float / m.total_count > 0.6 THEN 'bullish'
    WHEN m.falling_count::float / m.total_count > 0.6 THEN 'bearish'
    ELSE 'mixed'
  END as market_sentiment
FROM current_data c
JOIN volume_comparison v ON c.code = v.code
CROSS JOIN market_stats m
WHERE c.change_rate IS NOT NULL
ORDER BY 
  CASE $3
    WHEN 'gainers' THEN c.change_rate
    WHEN 'losers' THEN -c.change_rate  
    WHEN 'volume' THEN c.acc_trade_volume_24h
  END DESC
LIMIT $2;
```

---

## ⚡ Function 3: detect_anomalies

### 목적
이상 거래 패턴을 탐지하여 LLM에게 알림

### 입력 파라미터
- `timeframe`: 분석 기간 (기본값: "1h")
- `sensitivity`: 민감도 (1-5, 기본값: 3)

### 출력 (토큰 최적화)
```json
{
  "anomalies_found": 3,
  "alerts": [
    {
      "code": "KRW-SAFE", 
      "type": "volume_spike",
      "severity": "high",
      "current_volume": 140000000,
      "normal_volume": 45000000,
      "spike_ratio": 3.11,
      "description": "거래량이 평소의 3배 급증"
    },
    {
      "code": "KRW-XRP",
      "type": "price_volatility", 
      "severity": "medium",
      "price_change": 8.5,
      "time_period": "15min",
      "description": "15분간 8.5% 급등"
    }
  ],
  "market_health": "caution"
}
```

### SQL 쿼리 로직  
```sql
WITH recent_data AS (
  SELECT 
    code, trade_price, trade_volume, change_rate, time,
    LAG(trade_price) OVER (PARTITION BY code ORDER BY time) as prev_price,
    LAG(trade_volume) OVER (PARTITION BY code ORDER BY time) as prev_volume
  FROM ticker_data 
  WHERE time >= NOW() - INTERVAL '2 hours'
),
volume_anomalies AS (
  SELECT DISTINCT ON (v.code)
    v.code,
    'volume_spike' as anomaly_type,
    v.current_volume,
    v.avg_volume,
    v.spike_ratio,
    CASE 
      WHEN v.spike_ratio > 5 THEN 'critical'
      WHEN v.spike_ratio > 3 THEN 'high'  
      WHEN v.spike_ratio > 2 THEN 'medium'
      ELSE 'low'
    END as severity
  FROM volume_anomalies_1h v
  WHERE v.bucket >= NOW() - INTERVAL '1 hour'
    AND v.spike_count > 0
  ORDER BY v.code, v.bucket DESC
),
price_anomalies AS (
  SELECT 
    code,
    'price_volatility' as anomaly_type, 
    ABS(change_rate) as price_change,
    CASE 
      WHEN ABS(change_rate) > 15 THEN 'critical'
      WHEN ABS(change_rate) > 10 THEN 'high'
      WHEN ABS(change_rate) > 5 THEN 'medium'
      ELSE 'low'
    END as severity
  FROM recent_data
  WHERE time >= NOW() - INTERVAL '1 hour'
    AND ABS(change_rate) > (5.0 / $2)  -- sensitivity adjustment
)
SELECT 
  anomaly_type,
  code,
  severity,
  COALESCE(current_volume, 0) as current_volume,
  COALESCE(avg_volume, 0) as normal_volume, 
  COALESCE(spike_ratio, 0) as spike_ratio,
  COALESCE(price_change, 0) as price_change
FROM (
  SELECT * FROM volume_anomalies
  UNION ALL 
  SELECT 
    code, anomaly_type, 0, 0, 0, severity
  FROM price_anomalies
) anomalies
WHERE severity != 'low' OR $2 >= 4  -- sensitivity filter
ORDER BY 
  CASE severity 
    WHEN 'critical' THEN 1
    WHEN 'high' THEN 2  
    WHEN 'medium' THEN 3
    ELSE 4
  END;
```

---

## 🎯 토큰 효율성 달성 방법

### Before (Raw Data): ~50,000 토큰
```json
// 200개 코인 × 22개 필드 × 여러 시간대 = 거대한 JSON
{
  "KRW-BTC": {
    "time": "2025-01-14T10:30:00Z",
    "opening_price": 161740000.0,
    "high_price": 166292000.0,
    // ... 20개 더
  },
  // ... 199개 코인 더
}
```

### After (MCP Functions): ~500 토큰  
```json
// 계산된 핵심 지표만
{
  "coin_summary": { /* 10개 핵심 지표 */ },
  "market_movers": { /* 상위 10개만 */ },
  "anomalies": { /* 이상 상황만 */ }
}
```

### 🎉 결과: 99% 토큰 절약!