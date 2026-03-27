-- TimescaleDB 확장 활성화
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================
-- 1. tickers hypertable (raw data)
-- ============================================================
CREATE TABLE IF NOT EXISTS tickers (
    time         TIMESTAMPTZ      NOT NULL,
    code         TEXT             NOT NULL,
    trade_price  DOUBLE PRECISION NOT NULL,
    trade_volume DOUBLE PRECISION NOT NULL
);

SELECT create_hypertable('tickers', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_tickers_code_time ON tickers (code, time DESC);

-- ============================================================
-- 2. 1분 Continuous Aggregate
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS agg_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    code,
    first(trade_price, time)      AS open,
    max(trade_price)              AS high,
    min(trade_price)              AS low,
    last(trade_price, time)       AS close,
    sum(trade_volume)             AS volume,
    count(*)                      AS trade_count
FROM tickers
GROUP BY bucket, code
WITH NO DATA;

SELECT add_continuous_aggregate_policy('agg_1min',
    start_offset  => INTERVAL '2 hours',
    end_offset    => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);

-- ============================================================
-- 3. 5분 Continuous Aggregate
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS agg_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    code,
    first(trade_price, time)       AS open,
    max(trade_price)               AS high,
    min(trade_price)               AS low,
    last(trade_price, time)        AS close,
    sum(trade_volume)              AS volume,
    count(*)                       AS trade_count
FROM tickers
GROUP BY bucket, code
WITH NO DATA;

SELECT add_continuous_aggregate_policy('agg_5min',
    start_offset  => INTERVAL '6 hours',
    end_offset    => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE
);

-- ============================================================
-- 4. Rolling z-score view (24h window, per coin)
--    2단계: agg_1min 버킷 → 윈도우 함수로 rolling 통계
-- ============================================================
CREATE OR REPLACE VIEW v_zscore AS
WITH stats AS (
    SELECT
        bucket,
        code,
        close,
        volume,
        trade_count,
        -- 24시간 rolling 평균/표준편차 (1분 버킷 1440개)
        AVG(close) OVER w    AS avg_price,
        STDDEV(close) OVER w AS stddev_price,
        AVG(volume) OVER w   AS avg_volume,
        STDDEV(volume) OVER w AS stddev_volume,
        SUM(trade_count) OVER w AS total_trades_24h
    FROM agg_1min
    WINDOW w AS (
        PARTITION BY code
        ORDER BY bucket
        ROWS BETWEEN 1439 PRECEDING AND CURRENT ROW
    )
)
SELECT
    bucket,
    code,
    close        AS current_price,
    volume       AS current_volume,
    avg_price,
    stddev_price,
    avg_volume,
    stddev_volume,
    total_trades_24h,
    -- price z-score
    CASE
        WHEN stddev_price > 0 THEN (close - avg_price) / stddev_price
        ELSE 0
    END AS price_zscore,
    -- volume z-score
    CASE
        WHEN stddev_volume > 0 THEN (volume - avg_volume) / stddev_volume
        ELSE 0
    END AS volume_zscore
FROM stats
WHERE total_trades_24h >= 100;  -- 저유동 코인 필터

-- ============================================================
-- 5. incidents 테이블
-- ============================================================
CREATE TABLE IF NOT EXISTS incidents (
    incident_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    detected_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    coin_code        TEXT NOT NULL,
    anomaly_type     TEXT NOT NULL,
    severity         TEXT NOT NULL,
    z_score          DOUBLE PRECISION,           -- nullable: ensemble may not have z-score
    agent_report     JSONB,
    news_context     JSONB,
    confidence_score DOUBLE PRECISION,
    source           TEXT DEFAULT 'live',
    status           TEXT DEFAULT 'open',
    -- Ensemble fields
    ensemble_score      DOUBLE PRECISION,
    firing_indicators   TEXT[],                   -- e.g., {'zscore','rsi','bollinger_bands'}
    indicator_details   JSONB                     -- per-indicator detail snapshots
);

CREATE INDEX IF NOT EXISTS idx_incidents_detected ON incidents (detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_code ON incidents (coin_code);

-- ============================================================
-- 6. indicator_snapshots (Grafana 시각화용)
-- ============================================================
CREATE TABLE IF NOT EXISTS indicator_snapshots (
    time         TIMESTAMPTZ      NOT NULL,
    coin_code    TEXT             NOT NULL,
    indicator    TEXT             NOT NULL,   -- 'zscore', 'bollinger_bands', 'rsi', 'vwap'
    value        DOUBLE PRECISION,
    is_anomaly   BOOLEAN          DEFAULT FALSE,
    detail       JSONB
);

SELECT create_hypertable('indicator_snapshots', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_snapshots_code_time
    ON indicator_snapshots (coin_code, time DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_indicator
    ON indicator_snapshots (indicator, time DESC);
