-- =====================================================
-- Upbit Ticker Data - Complete Schema (22 fields)
-- =====================================================

-- ENUM Types for efficient storage
CREATE TYPE market_change_type AS ENUM ('RISE', 'FALL', 'EVEN');
CREATE TYPE market_ask_bid_type AS ENUM ('ASK', 'BID');
CREATE TYPE market_state_type AS ENUM ('ACTIVE', 'DELISTED', 'SUSPENDED');
CREATE TYPE market_warning_type AS ENUM ('NONE', 'CAUTION', 'WARNING', 'DANGER');
CREATE TYPE stream_type_enum AS ENUM ('REALTIME', 'SNAPSHOT');

-- Drop existing table if exists
DROP TABLE IF EXISTS ticker_data CASCADE;

-- Create new ticker_data table with all 22 fields
CREATE TABLE ticker_data (
    -- Primary fields
    time TIMESTAMPTZ NOT NULL,
    code TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'ticker',
    
    -- Price fields (using DECIMAL for precision)
    opening_price DECIMAL(20,8) NOT NULL,
    high_price DECIMAL(20,8) NOT NULL,
    low_price DECIMAL(20,8) NOT NULL,
    trade_price DECIMAL(20,8) NOT NULL,
    prev_closing_price DECIMAL(20,8) NOT NULL,
    
    -- Price change fields
    change market_change_type NOT NULL,
    change_price DECIMAL(20,8) NOT NULL,
    signed_change_price DECIMAL(20,8) NOT NULL,
    change_rate DECIMAL(10,8) NOT NULL,
    signed_change_rate DECIMAL(10,8) NOT NULL,
    
    -- Volume and trading fields
    trade_volume DECIMAL(20,8) NOT NULL,
    acc_trade_volume DECIMAL(20,8) NOT NULL,
    acc_trade_price DECIMAL(25,8) NOT NULL,
    ask_bid market_ask_bid_type NOT NULL,
    acc_ask_volume DECIMAL(20,8) NOT NULL,
    acc_bid_volume DECIMAL(20,8) NOT NULL,
    
    -- 24h accumulation fields
    acc_trade_price_24h DECIMAL(25,8) NOT NULL,
    acc_trade_volume_24h DECIMAL(20,8) NOT NULL,
    
    -- 52-week high/low fields
    highest_52_week_price DECIMAL(20,8) NOT NULL,
    highest_52_week_date DATE NOT NULL,
    lowest_52_week_price DECIMAL(20,8) NOT NULL,
    lowest_52_week_date DATE NOT NULL,
    
    -- Market status fields
    market_state market_state_type NOT NULL DEFAULT 'ACTIVE',
    market_warning market_warning_type NOT NULL DEFAULT 'NONE',
    is_trading_suspended BOOLEAN NOT NULL DEFAULT FALSE,
    delisting_date DATE NULL,
    
    -- Timestamp fields
    trade_date TEXT NOT NULL,
    trade_time TEXT NOT NULL,
    trade_timestamp BIGINT NOT NULL,
    timestamp BIGINT NOT NULL,
    stream_type stream_type_enum NOT NULL DEFAULT 'REALTIME',
    
    -- Constraints
    PRIMARY KEY (time, code)
);

-- Create TimescaleDB hypertable
SELECT create_hypertable('ticker_data', 'time', if_not_exists => TRUE);

-- Create indexes for efficient querying
CREATE INDEX idx_ticker_data_code_time ON ticker_data (code, time DESC);
CREATE INDEX idx_ticker_data_timestamp ON ticker_data (timestamp);
CREATE INDEX idx_ticker_data_trade_timestamp ON ticker_data (trade_timestamp);
CREATE INDEX idx_ticker_data_change_type ON ticker_data (change);
CREATE INDEX idx_ticker_data_market_state ON ticker_data (market_state);

-- Create indexes for anomaly detection
CREATE INDEX idx_ticker_data_volume_spike ON ticker_data (code, trade_volume DESC);
CREATE INDEX idx_ticker_data_price_change ON ticker_data (code, change_rate DESC);

-- Comments for documentation
COMMENT ON TABLE ticker_data IS 'Complete Upbit ticker data with all 22 fields for LLM analytics';
COMMENT ON COLUMN ticker_data.time IS 'Processed timestamp (derived from trade_timestamp)';
COMMENT ON COLUMN ticker_data.trade_timestamp IS 'Original trade timestamp from Upbit';
COMMENT ON COLUMN ticker_data.timestamp IS 'WebSocket message timestamp';
COMMENT ON COLUMN ticker_data.change_rate IS 'Price change rate (0.0404 = 4.04%)';
COMMENT ON COLUMN ticker_data.acc_trade_price IS 'Accumulated trade price for the day';
COMMENT ON COLUMN ticker_data.acc_trade_volume IS 'Accumulated trade volume for the day';

-- Sample query for testing
-- SELECT code, trade_price, change_rate, trade_volume 
-- FROM ticker_data 
-- WHERE code = 'KRW-BTC' 
-- ORDER BY time DESC 
-- LIMIT 10;