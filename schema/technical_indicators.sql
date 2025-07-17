-- =====================================================
-- Technical Indicators: RSI and Bollinger Bands
-- =====================================================

-- Function: calculate_rsi
-- RSI (Relative Strength Index) 계산
-- 기본 14 기간 사용, 0-100 범위 값 반환
CREATE OR REPLACE FUNCTION calculate_rsi(
    coin_code TEXT,
    period INTEGER DEFAULT 14
)
RETURNS TABLE (
    code TEXT,
    "time" TIMESTAMPTZ,
    price DECIMAL,
    rsi DECIMAL,
    signal TEXT,
    strength TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH price_data AS (
        SELECT 
            t.code,
            t.time,
            t.trade_price,
            LAG(t.trade_price) OVER (ORDER BY t.time) as prev_price
        FROM ticker_data t
        WHERE t.code = coin_code
          AND t.time >= NOW() - INTERVAL '7 days'
        ORDER BY t.time
    ),
    price_changes AS (
        SELECT 
            p.code,
            p.time,
            p.trade_price,
            CASE 
                WHEN p.trade_price > p.prev_price THEN p.trade_price - p.prev_price
                ELSE 0
            END as gain,
            CASE 
                WHEN p.trade_price < p.prev_price THEN p.prev_price - p.trade_price
                ELSE 0
            END as loss
        FROM price_data p
        WHERE p.prev_price IS NOT NULL
    ),
    rsi_calculation AS (
        SELECT 
            pc.code,
            pc.time,
            pc.trade_price,
            AVG(pc.gain) OVER (ORDER BY pc.time ROWS BETWEEN period-1 PRECEDING AND CURRENT ROW) as avg_gain,
            AVG(pc.loss) OVER (ORDER BY pc.time ROWS BETWEEN period-1 PRECEDING AND CURRENT ROW) as avg_loss,
            ROW_NUMBER() OVER (ORDER BY pc.time) as row_num
        FROM price_changes pc
    ),
    rsi_values AS (
        SELECT 
            rc.code,
            rc.time,
            rc.trade_price,
            CASE 
                WHEN rc.avg_loss = 0 THEN 100
                WHEN rc.avg_gain = 0 THEN 0
                ELSE 100 - (100 / (1 + (rc.avg_gain / rc.avg_loss)))
            END as rsi_value
        FROM rsi_calculation rc
        WHERE rc.row_num >= period
    )
    SELECT 
        r.code,
        r.time,
        r.trade_price,
        ROUND(r.rsi_value, 2),
        CASE 
            WHEN r.rsi_value > 70 THEN 'overbought'
            WHEN r.rsi_value < 30 THEN 'oversold'
            WHEN r.rsi_value > 50 THEN 'bullish'
            ELSE 'bearish'
        END,
        CASE 
            WHEN r.rsi_value > 80 THEN 'very_strong'
            WHEN r.rsi_value > 60 THEN 'strong'
            WHEN r.rsi_value > 40 THEN 'moderate'
            WHEN r.rsi_value > 20 THEN 'weak'
            ELSE 'very_weak'
        END
    FROM rsi_values r
    ORDER BY r.time DESC
    LIMIT 100;
END;
$$ LANGUAGE plpgsql;

-- Function: calculate_bollinger_bands
-- 볼린저밴드 계산 (중간선, 상단선, 하단선)
-- 기본 20 기간, 2 표준편차 사용
CREATE OR REPLACE FUNCTION calculate_bollinger_bands(
    coin_code TEXT,
    period INTEGER DEFAULT 20,
    std_dev DECIMAL DEFAULT 2.0
)
RETURNS TABLE (
    code TEXT,
    "time" TIMESTAMPTZ,
    price DECIMAL,
    middle_band DECIMAL,
    upper_band DECIMAL,
    lower_band DECIMAL,
    band_width DECIMAL,
    position_pct DECIMAL,
    signal TEXT,
    squeeze BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    WITH price_data AS (
        SELECT 
            t.code,
            t.time,
            t.trade_price
        FROM ticker_data t
        WHERE t.code = coin_code
          AND t.time >= NOW() - INTERVAL '7 days'
        ORDER BY t.time
    ),
    bollinger_calculation AS (
        SELECT 
            pd.code,
            pd.time,
            pd.trade_price,
            AVG(pd.trade_price) OVER (ORDER BY pd.time ROWS BETWEEN period-1 PRECEDING AND CURRENT ROW) as sma,
            STDDEV(pd.trade_price) OVER (ORDER BY pd.time ROWS BETWEEN period-1 PRECEDING AND CURRENT ROW) as stddev_price,
            ROW_NUMBER() OVER (ORDER BY pd.time) as row_num
        FROM price_data pd
    ),
    bollinger_bands AS (
        SELECT 
            bc.code,
            bc.time,
            bc.trade_price,
            bc.sma as middle_line,
            bc.sma + (bc.stddev_price * std_dev) as upper_line,
            bc.sma - (bc.stddev_price * std_dev) as lower_line,
            (bc.stddev_price * std_dev * 2) as band_width_val,
            bc.stddev_price
        FROM bollinger_calculation bc
        WHERE bc.row_num >= period
    ),
    bollinger_signals AS (
        SELECT 
            bb.code,
            bb.time,
            bb.trade_price,
            bb.middle_line,
            bb.upper_line,
            bb.lower_line,
            bb.band_width_val,
            CASE 
                WHEN (bb.upper_line - bb.lower_line) > 0 
                THEN ((bb.trade_price - bb.lower_line) / (bb.upper_line - bb.lower_line)) * 100
                ELSE 50
            END as position_percentage,
            CASE 
                WHEN bb.trade_price > bb.upper_line THEN 'sell'
                WHEN bb.trade_price < bb.lower_line THEN 'buy'
                WHEN bb.trade_price > bb.middle_line THEN 'neutral_bullish'
                ELSE 'neutral_bearish'
            END as band_signal,
            bb.stddev_price < (bb.middle_line * 0.02) as is_squeeze  -- 2% 기준으로 스퀴즈 판단
        FROM bollinger_bands bb
    )
    SELECT 
        b.code,
        b.time,
        b.trade_price,
        ROUND(b.middle_line, 2),
        ROUND(b.upper_line, 2),
        ROUND(b.lower_line, 2),
        ROUND(b.band_width_val, 2),
        ROUND(b.position_percentage, 2),
        b.band_signal,
        b.is_squeeze
    FROM bollinger_signals b
    ORDER BY b.time DESC
    LIMIT 100;
END;
$$ LANGUAGE plpgsql;

-- Function: get_technical_analysis
-- 종합 기술적 분석 (RSI + 볼린저밴드 + 이동평균)
CREATE OR REPLACE FUNCTION get_technical_analysis(
    coin_code TEXT,
    analysis_period INTEGER DEFAULT 1  -- hours
)
RETURNS TABLE (
    code TEXT,
    current_price DECIMAL,
    rsi DECIMAL,
    rsi_signal TEXT,
    bb_position DECIMAL,
    bb_signal TEXT,
    sma_5 DECIMAL,
    sma_20 DECIMAL,
    trend_signal TEXT,
    overall_signal TEXT,
    confidence_score INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH latest_data AS (
        SELECT DISTINCT ON (t.code)
            t.code,
            t.trade_price,
            t.time
        FROM ticker_data t
        WHERE t.code = coin_code
          AND t.time >= NOW() - (analysis_period || ' hours')::INTERVAL
        ORDER BY t.code, t.time DESC
    ),
    rsi_data AS (
        SELECT 
            r.rsi,
            r.signal as rsi_sig
        FROM calculate_rsi(coin_code, 14) r
        ORDER BY r.time DESC
        LIMIT 1
    ),
    bb_data AS (
        SELECT 
            b.position_pct,
            b.signal as bb_sig
        FROM calculate_bollinger_bands(coin_code, 20, 2.0) b
        ORDER BY b.time DESC
        LIMIT 1
    ),
    sma_data AS (
        SELECT 
            AVG(CASE WHEN rn <= 5 THEN trade_price END) as sma5,
            AVG(CASE WHEN rn <= 20 THEN trade_price END) as sma20
        FROM (
            SELECT 
                trade_price,
                ROW_NUMBER() OVER (ORDER BY time DESC) as rn
            FROM ticker_data td
            WHERE td.code = coin_code
              AND td.time >= NOW() - INTERVAL '2 hours'
        ) t
    ),
    combined_analysis AS (
        SELECT 
            l.code,
            l.trade_price,
            COALESCE(r.rsi, 50) as rsi_val,
            COALESCE(r.rsi_sig, 'neutral') as rsi_signal_val,
            COALESCE(b.position_pct, 50) as bb_position_val,
            COALESCE(b.bb_sig, 'neutral') as bb_signal_val,
            s.sma5,
            s.sma20,
            CASE 
                WHEN s.sma5 > s.sma20 THEN 'bullish'
                WHEN s.sma5 < s.sma20 THEN 'bearish'
                ELSE 'neutral'
            END as trend_sig
        FROM latest_data l
        CROSS JOIN rsi_data r
        CROSS JOIN bb_data b
        CROSS JOIN sma_data s
    )
    SELECT 
        c.code,
        c.trade_price,
        c.rsi_val,
        c.rsi_signal_val,
        c.bb_position_val,
        c.bb_signal_val,
        ROUND(c.sma5, 2),
        ROUND(c.sma20, 2),
        c.trend_sig,
        CASE 
            WHEN c.rsi_signal_val = 'overbought' AND c.bb_signal_val = 'sell' THEN 'strong_sell'
            WHEN c.rsi_signal_val = 'oversold' AND c.bb_signal_val = 'buy' THEN 'strong_buy'
            WHEN c.trend_sig = 'bullish' AND c.rsi_val > 50 THEN 'buy'
            WHEN c.trend_sig = 'bearish' AND c.rsi_val < 50 THEN 'sell'
            ELSE 'hold'
        END,
        CASE 
            WHEN c.rsi_signal_val IN ('overbought', 'oversold') 
                 AND c.bb_signal_val IN ('buy', 'sell') THEN 85
            WHEN c.trend_sig != 'neutral' 
                 AND c.rsi_signal_val IN ('bullish', 'bearish') THEN 70
            ELSE 50
        END
    FROM combined_analysis c;
END;
$$ LANGUAGE plpgsql;

-- 함수 권한 설정
GRANT EXECUTE ON FUNCTION calculate_rsi(TEXT, INTEGER) TO PUBLIC;
GRANT EXECUTE ON FUNCTION calculate_bollinger_bands(TEXT, INTEGER, DECIMAL) TO PUBLIC;
GRANT EXECUTE ON FUNCTION get_technical_analysis(TEXT, INTEGER) TO PUBLIC;

-- 사용 예시 주석
/*
-- 사용 예시:

-- 1. BTC RSI 계산 (14 기간)
SELECT * FROM calculate_rsi('KRW-BTC', 14) ORDER BY time DESC LIMIT 10;

-- 2. BTC 볼린저밴드 계산 (20 기간, 2 표준편차)
SELECT * FROM calculate_bollinger_bands('KRW-BTC', 20, 2.0) ORDER BY time DESC LIMIT 10;

-- 3. BTC 종합 기술적 분석
SELECT * FROM get_technical_analysis('KRW-BTC', 1);
*/