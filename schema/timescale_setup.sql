-- =====================================================
-- TimescaleDB Setup and Configuration for Upbit Analytics
-- =====================================================

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Set optimal TimescaleDB configurations
-- Optimize for time-series workloads
SET timescaledb.max_background_workers = 8;

-- Create database-level configurations for TimescaleDB
-- Note: These should be set in postgresql.conf for production

-- =====================================================
-- Continuous Aggregates for LLM Analytics
-- =====================================================

-- 1. OHLCV 1-minute aggregates (for technical analysis)
CREATE MATERIALIZED VIEW ohlcv_1m
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 minute', time) AS bucket,
    code,
    first(trade_price, time) AS open,
    max(trade_price) AS high,
    min(trade_price) AS low,
    last(trade_price, time) AS close,
    sum(trade_volume) AS volume,
    count(*) AS trade_count
FROM ticker_data
GROUP BY bucket, code;

-- Create refresh policy for 1-minute OHLCV
SELECT add_continuous_aggregate_policy('ohlcv_1m',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');

-- 2. Market summary 5-minute aggregates (for market overview)
CREATE MATERIALIZED VIEW market_summary_5m
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('5 minutes', time) AS bucket,
    count(DISTINCT code) AS total_coins,
    count(*) FILTER (WHERE change = 'RISE') AS rising_coins,
    count(*) FILTER (WHERE change = 'FALL') AS falling_coins,
    count(*) FILTER (WHERE change = 'EVEN') AS neutral_coins,
    avg(change_rate) AS avg_change_rate,
    sum(acc_trade_price_24h) AS total_market_cap_24h,
    sum(trade_volume) AS total_volume
FROM ticker_data
GROUP BY bucket;

-- Create refresh policy for market summary
SELECT add_continuous_aggregate_policy('market_summary_5m',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes');

-- 3. Anomaly detection aggregates (for unusual activity)
CREATE MATERIALIZED VIEW volume_anomalies_1h
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', time) AS bucket,
    code,
    avg(trade_volume) AS avg_volume,
    stddev(trade_volume) AS stddev_volume,
    max(trade_volume) AS max_volume,
    count(*) FILTER (WHERE trade_volume > (avg(trade_volume) + 2 * stddev(trade_volume))) AS spike_count
FROM ticker_data
GROUP BY bucket, code;

-- Create refresh policy for volume anomalies
SELECT add_continuous_aggregate_policy('volume_anomalies_1h',
    start_offset => INTERVAL '24 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- =====================================================
-- Optimized Indexes for LLM Queries
-- =====================================================

-- Composite indexes for efficient MCP queries
CREATE INDEX CONCURRENTLY idx_ticker_latest_by_code 
ON ticker_data (code, time DESC) 
INCLUDE (trade_price, change_rate, trade_volume);

-- Index for anomaly detection
CREATE INDEX CONCURRENTLY idx_ticker_volume_analysis 
ON ticker_data (code, trade_volume DESC, time DESC);

-- Index for price movement analysis
CREATE INDEX CONCURRENTLY idx_ticker_price_movements 
ON ticker_data (change_rate DESC, time DESC) 
INCLUDE (code, trade_price);

-- Index for 52-week analysis
CREATE INDEX CONCURRENTLY idx_ticker_52week_analysis 
ON ticker_data (code) 
INCLUDE (highest_52_week_price, lowest_52_week_price, trade_price);

-- =====================================================
-- Retention Policies (for data management)
-- =====================================================

-- Keep raw ticker data for 30 days
SELECT add_retention_policy('ticker_data', INTERVAL '30 days');

-- Keep 1-minute OHLCV for 90 days
SELECT add_retention_policy('ohlcv_1m', INTERVAL '90 days');

-- Keep market summaries for 1 year
SELECT add_retention_policy('market_summary_5m', INTERVAL '1 year');

-- Keep volume anomalies for 6 months
SELECT add_retention_policy('volume_anomalies_1h', INTERVAL '6 months');

-- =====================================================
-- Compression Policies (for storage optimization)
-- =====================================================

-- Compress ticker data older than 7 days
SELECT add_compression_policy('ticker_data', INTERVAL '7 days');

-- Compress aggregates older than 1 day
SELECT add_compression_policy('ohlcv_1m', INTERVAL '1 day');
SELECT add_compression_policy('market_summary_5m', INTERVAL '1 day');
SELECT add_compression_policy('volume_anomalies_1h', INTERVAL '1 day');

-- =====================================================
-- Utility Functions for LLM Analytics
-- =====================================================

-- Function to get latest market snapshot
CREATE OR REPLACE FUNCTION get_latest_market_snapshot()
RETURNS TABLE (
    code TEXT,
    current_price DECIMAL,
    change_rate DECIMAL,
    volume_24h DECIMAL,
    market_cap_24h DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT ON (t.code)
        t.code,
        t.trade_price,
        t.change_rate,
        t.acc_trade_volume_24h,
        t.acc_trade_price_24h
    FROM ticker_data t
    ORDER BY t.code, t.time DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to detect volume spikes
CREATE OR REPLACE FUNCTION detect_volume_spikes(threshold_multiplier DECIMAL DEFAULT 3.0)
RETURNS TABLE (
    code TEXT,
    current_volume DECIMAL,
    avg_volume DECIMAL,
    spike_ratio DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    WITH volume_stats AS (
        SELECT 
            t.code,
            t.trade_volume as current_volume,
            AVG(t.trade_volume) OVER (
                PARTITION BY t.code 
                ORDER BY t.time 
                ROWS BETWEEN 100 PRECEDING AND 1 PRECEDING
            ) as avg_volume
        FROM ticker_data t
        WHERE t.time >= NOW() - INTERVAL '1 hour'
    )
    SELECT 
        vs.code,
        vs.current_volume,
        vs.avg_volume,
        vs.current_volume / NULLIF(vs.avg_volume, 0) as spike_ratio
    FROM volume_stats vs
    WHERE vs.current_volume > (vs.avg_volume * threshold_multiplier)
    ORDER BY spike_ratio DESC;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Performance Monitoring Views
-- =====================================================

-- View for monitoring hypertable statistics
CREATE VIEW hypertable_stats AS
SELECT 
    ht.table_name,
    ht.num_chunks,
    pg_size_pretty(total_bytes) AS total_size,
    pg_size_pretty(index_bytes) AS index_size,
    pg_size_pretty(toast_bytes) AS toast_size,
    pg_size_pretty(total_bytes - index_bytes - COALESCE(toast_bytes, 0)) AS table_size
FROM timescaledb_information.hypertables ht
JOIN timescaledb_information.hypertable_detailed_size hds 
ON ht.table_name = hds.table_name;

-- View for continuous aggregate refresh status
CREATE VIEW continuous_aggregate_status AS
SELECT 
    cagg.view_name,
    cagg.refresh_lag,
    cagg.materialized_only,
    cjb.last_run_started_at,
    cjb.last_run_duration
FROM timescaledb_information.continuous_aggregates cagg
LEFT JOIN timescaledb_information.jobs j ON j.hypertable_name = cagg.view_name
LEFT JOIN timescaledb_information.job_stats cjb ON j.job_id = cjb.job_id;

-- =====================================================
-- Initial Data Validation
-- =====================================================

-- Test function to validate data integrity
CREATE OR REPLACE FUNCTION validate_ticker_data()
RETURNS TABLE (
    check_name TEXT,
    status TEXT,
    details TEXT
) AS $$
BEGIN
    -- Check if hypertable was created successfully
    RETURN QUERY
    SELECT 
        'hypertable_creation' as check_name,
        CASE WHEN EXISTS(
            SELECT 1 FROM timescaledb_information.hypertables 
            WHERE table_name = 'ticker_data'
        ) THEN 'PASS' ELSE 'FAIL' END as status,
        'TimescaleDB hypertable setup' as details;
    
    -- Check for ENUM types
    RETURN QUERY
    SELECT 
        'enum_types' as check_name,
        CASE WHEN EXISTS(
            SELECT 1 FROM pg_type 
            WHERE typname IN ('market_change_type', 'market_ask_bid_type', 'market_state_type')
        ) THEN 'PASS' ELSE 'FAIL' END as status,
        'Required ENUM types exist' as details;
    
    -- Check if continuous aggregates exist
    RETURN QUERY
    SELECT 
        'continuous_aggregates' as check_name,
        CASE WHEN EXISTS(
            SELECT 1 FROM timescaledb_information.continuous_aggregates 
            WHERE view_name IN ('ohlcv_1m', 'market_summary_5m', 'volume_anomalies_1h')
        ) THEN 'PASS' ELSE 'FAIL' END as status,
        'Continuous aggregates created' as details;
END;
$$ LANGUAGE plpgsql;

-- Run validation
SELECT * FROM validate_ticker_data();