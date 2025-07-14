-- =====================================================
-- Migration Script: trade_data -> ticker_data (4 fields -> 22 fields)
-- =====================================================

-- Step 1: Backup existing data
CREATE TABLE trade_data_backup AS SELECT * FROM trade_data;

-- Verify backup
SELECT COUNT(*) as total_records FROM trade_data_backup;
SELECT 
    MIN(time) as earliest_record,
    MAX(time) as latest_record,
    COUNT(DISTINCT code) as unique_codes
FROM trade_data_backup;

-- Step 2: Check if we have the required ENUM types
-- (Run the ticker_data_schema.sql first if these don't exist)

-- Step 3: Create new ticker_data table
-- (This is defined in ticker_data_schema.sql)

-- Step 4: Migration queries
-- Since the old table only has 4 fields (time, code, trade_price, trade_volume),
-- we'll need to populate missing fields with reasonable defaults

-- Note: This migration script is for reference only.
-- The actual migration should be done carefully with real data analysis.

-- Example migration query (DO NOT RUN without data analysis):
/*
INSERT INTO ticker_data (
    time,
    code,
    type,
    opening_price,
    high_price,
    low_price,
    trade_price,
    prev_closing_price,
    change,
    change_price,
    signed_change_price,
    change_rate,
    signed_change_rate,
    trade_volume,
    acc_trade_volume,
    acc_trade_price,
    ask_bid,
    acc_ask_volume,
    acc_bid_volume,
    acc_trade_price_24h,
    acc_trade_volume_24h,
    highest_52_week_price,
    highest_52_week_date,
    lowest_52_week_price,
    lowest_52_week_date,
    market_state,
    market_warning,
    is_trading_suspended,
    delisting_date,
    trade_date,
    trade_time,
    trade_timestamp,
    timestamp,
    stream_type
)
SELECT 
    time,
    code,
    'ticker' as type,
    trade_price as opening_price,  -- Approximate
    trade_price as high_price,     -- Approximate
    trade_price as low_price,      -- Approximate
    trade_price,
    trade_price as prev_closing_price,  -- Approximate
    'EVEN'::market_change_type as change,  -- Default
    0.0 as change_price,
    0.0 as signed_change_price,
    0.0 as change_rate,
    0.0 as signed_change_rate,
    trade_volume,
    trade_volume as acc_trade_volume,  -- Approximate
    (trade_price * trade_volume) as acc_trade_price,  -- Approximate
    'BID'::market_ask_bid_type as ask_bid,  -- Default
    trade_volume / 2 as acc_ask_volume,  -- Approximate
    trade_volume / 2 as acc_bid_volume,  -- Approximate
    (trade_price * trade_volume) as acc_trade_price_24h,  -- Approximate
    trade_volume as acc_trade_volume_24h,  -- Approximate
    trade_price * 1.5 as highest_52_week_price,  -- Approximate
    CURRENT_DATE - INTERVAL '180 days' as highest_52_week_date,  -- Approximate
    trade_price * 0.5 as lowest_52_week_price,  -- Approximate
    CURRENT_DATE - INTERVAL '180 days' as lowest_52_week_date,  -- Approximate
    'ACTIVE'::market_state_type as market_state,
    'NONE'::market_warning_type as market_warning,
    FALSE as is_trading_suspended,
    NULL as delisting_date,
    TO_CHAR(time, 'YYYYMMDD') as trade_date,
    TO_CHAR(time, 'HH24MISS') as trade_time,
    EXTRACT(EPOCH FROM time) * 1000 as trade_timestamp,
    EXTRACT(EPOCH FROM time) * 1000 as timestamp,
    'REALTIME'::stream_type_enum as stream_type
FROM trade_data_backup;
*/

-- Step 5: Verification queries
-- After migration, run these to verify data integrity

-- Count comparison
-- SELECT 'old_table' as source, COUNT(*) as count FROM trade_data_backup
-- UNION ALL
-- SELECT 'new_table' as source, COUNT(*) as count FROM ticker_data;

-- Data sample comparison
-- SELECT 'old_data' as source, time, code, trade_price, trade_volume 
-- FROM trade_data_backup 
-- ORDER BY time DESC 
-- LIMIT 5;

-- SELECT 'new_data' as source, time, code, trade_price, trade_volume 
-- FROM ticker_data 
-- ORDER BY time DESC 
-- LIMIT 5;

-- Step 6: Cleanup (only after verification)
-- DROP TABLE trade_data_backup;

-- Notes:
-- 1. This migration uses approximations for missing fields
-- 2. For production, consider collecting real data for all 22 fields first
-- 3. Test migration on a small dataset before full migration
-- 4. Monitor performance after migration