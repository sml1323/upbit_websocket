-- TimescaleDB 확장 활성화
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- tickers hypertable
CREATE TABLE IF NOT EXISTS tickers (
    time         TIMESTAMPTZ NOT NULL,
    code         TEXT        NOT NULL,
    trade_price  DOUBLE PRECISION NOT NULL,
    trade_volume DOUBLE PRECISION NOT NULL
);

SELECT create_hypertable('tickers', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_tickers_code_time ON tickers (code, time DESC);
