-- =====================================================
-- MCP 함수들: LLM을 위한 토큰 최적화 데이터 제공
-- =====================================================

-- Function 1: get_coin_summary
-- 특정 코인의 현재 상태 요약 (토큰 최적화)
CREATE OR REPLACE FUNCTION get_coin_summary(
    coin_code TEXT,
    timeframe_hours INTEGER DEFAULT 1
)
RETURNS TABLE (
    code TEXT,
    current_price DECIMAL,
    change_rate DECIMAL,
    trend TEXT,
    volume_spike BOOLEAN,
    support_level DECIMAL,
    resistance_level DECIMAL,
    rsi_signal TEXT,
    volatility TEXT,
    market_cap_rank TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH latest_data AS (
        SELECT DISTINCT ON (t.code)
            t.code,
            t.trade_price,
            t.change_rate,
            t.trade_volume,
            t.highest_52_week_price,
            t.lowest_52_week_price,
            t.acc_trade_volume_24h
        FROM ticker_data t
        WHERE t.code = coin_code 
          AND t.time >= NOW() - (timeframe_hours || ' hours')::INTERVAL
        ORDER BY t.code, t.time DESC
    ),
    volume_analysis AS (
        SELECT 
            AVG(t.trade_volume) as avg_volume,
            STDDEV(t.trade_volume) as volume_stddev
        FROM ticker_data t
        WHERE t.code = coin_code 
          AND t.time >= NOW() - INTERVAL '24 hours'
    )
    SELECT 
        l.code,
        l.trade_price,
        l.change_rate,
        CASE 
            WHEN l.change_rate > 3 THEN 'bullish'
            WHEN l.change_rate < -3 THEN 'bearish'
            ELSE 'neutral'
        END,
        l.trade_volume > (v.avg_volume + 2 * COALESCE(v.volume_stddev, 0)),
        l.lowest_52_week_price * 1.02,
        l.highest_52_week_price * 0.98,
        CASE 
            WHEN l.change_rate > 5 THEN 'overbought'
            WHEN l.change_rate < -5 THEN 'oversold'
            ELSE 'neutral'
        END,
        CASE 
            WHEN ABS(l.change_rate) > 10 THEN 'high'
            WHEN ABS(l.change_rate) > 3 THEN 'medium'
            ELSE 'low'
        END,
        CASE 
            WHEN l.acc_trade_volume_24h > 1000000000 THEN 'large'
            WHEN l.acc_trade_volume_24h > 100000000 THEN 'medium'
            ELSE 'small'
        END
    FROM latest_data l
    CROSS JOIN volume_analysis v;
END;
$$ LANGUAGE plpgsql;

-- Function 2: get_market_movers  
-- 시장에서 가장 활발한 코인들 (토큰 최적화)
CREATE OR REPLACE FUNCTION get_market_movers(
    move_type TEXT DEFAULT 'gainers',
    result_limit INTEGER DEFAULT 10,
    timeframe_hours INTEGER DEFAULT 1
)
RETURNS TABLE (
    code TEXT,
    price DECIMAL,
    change_rate DECIMAL,
    volume_change DECIMAL,
    momentum TEXT,
    market_sentiment TEXT,
    total_rising INTEGER,
    total_falling INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH current_data AS (
        SELECT DISTINCT ON (t.code)
            t.code,
            t.trade_price,
            t.change_rate,
            t.acc_trade_volume_24h,
            t.time
        FROM ticker_data t
        WHERE t.time >= NOW() - (timeframe_hours || ' hours')::INTERVAL
        ORDER BY t.code, t.time DESC
    ),
    volume_comparison AS (
        SELECT 
            t.code,
            AVG(t.acc_trade_volume_24h) as avg_volume_24h
        FROM ticker_data t
        WHERE t.time >= NOW() - INTERVAL '7 days'
        GROUP BY t.code
    ),
    market_stats AS (
        SELECT 
            COUNT(*) FILTER (WHERE change_rate > 0) as rising_count,
            COUNT(*) FILTER (WHERE change_rate < 0) as falling_count,
            COUNT(*) as total_count
        FROM current_data
    ),
    ranked_data AS (
        SELECT 
            c.code,
            c.trade_price,
            c.change_rate,
            COALESCE(c.acc_trade_volume_24h / NULLIF(v.avg_volume_24h, 0) * 100, 100) as volume_change_pct,
            CASE 
                WHEN c.change_rate > 10 THEN 'very_strong'
                WHEN c.change_rate > 5 THEN 'strong'
                WHEN c.change_rate > 1 THEN 'moderate'
                ELSE 'weak'
            END as momentum_level,
            m.rising_count,
            m.falling_count,
            CASE 
                WHEN m.rising_count::float / NULLIF(m.total_count, 0) > 0.6 THEN 'bullish'
                WHEN m.falling_count::float / NULLIF(m.total_count, 0) > 0.6 THEN 'bearish'
                ELSE 'mixed'
            END as sentiment,
            ROW_NUMBER() OVER (
                ORDER BY 
                    CASE move_type
                        WHEN 'gainers' THEN c.change_rate
                        WHEN 'losers' THEN -c.change_rate
                        WHEN 'volume' THEN c.acc_trade_volume_24h
                        ELSE c.change_rate
                    END DESC
            ) as rank
        FROM current_data c
        LEFT JOIN volume_comparison v ON c.code = v.code
        CROSS JOIN market_stats m
        WHERE c.change_rate IS NOT NULL
    )
    SELECT 
        r.code,
        r.trade_price,
        r.change_rate,
        r.volume_change_pct,
        r.momentum_level,
        r.sentiment,
        r.rising_count,
        r.falling_count
    FROM ranked_data r
    WHERE r.rank <= result_limit;
END;
$$ LANGUAGE plpgsql;

-- Function 3: detect_anomalies
-- 이상 거래 패턴 탐지 (토큰 최적화)
CREATE OR REPLACE FUNCTION detect_anomalies(
    timeframe_hours INTEGER DEFAULT 1,
    sensitivity INTEGER DEFAULT 3
)
RETURNS TABLE (
    anomaly_type TEXT,
    code TEXT,
    severity TEXT,
    current_volume DECIMAL,
    normal_volume DECIMAL,
    spike_ratio DECIMAL,
    price_change DECIMAL,
    description TEXT
) AS $$
DECLARE
    sensitivity_multiplier DECIMAL;
BEGIN
    -- 민감도에 따른 임계값 조정
    sensitivity_multiplier := CASE sensitivity
        WHEN 1 THEN 0.2  -- 매우 낮음 (큰 변화만)
        WHEN 2 THEN 0.4  -- 낮음
        WHEN 3 THEN 1.0  -- 보통  
        WHEN 4 THEN 1.5  -- 높음
        WHEN 5 THEN 2.0  -- 매우 높음 (작은 변화도)
        ELSE 1.0
    END;

    RETURN QUERY
    WITH recent_data AS (
        SELECT DISTINCT ON (t.code)
            t.code,
            t.trade_price,
            t.trade_volume,
            t.change_rate,
            t.time
        FROM ticker_data t
        WHERE t.time >= NOW() - (timeframe_hours || ' hours')::INTERVAL
        ORDER BY t.code, t.time DESC
    ),
    volume_baseline AS (
        SELECT 
            t.code,
            AVG(t.trade_volume) as avg_volume,
            STDDEV(t.trade_volume) as volume_stddev
        FROM ticker_data t
        WHERE t.time >= NOW() - INTERVAL '7 days'
          AND t.time < NOW() - (timeframe_hours || ' hours')::INTERVAL
        GROUP BY t.code
    ),
    volume_anomalies AS (
        SELECT 
            'volume_spike' as anomaly_type,
            r.code,
            CASE 
                WHEN r.trade_volume > (v.avg_volume + 5 * COALESCE(v.volume_stddev, 0)) THEN 'critical'
                WHEN r.trade_volume > (v.avg_volume + 3 * COALESCE(v.volume_stddev, 0)) THEN 'high'
                WHEN r.trade_volume > (v.avg_volume + 2 * COALESCE(v.volume_stddev, 0)) THEN 'medium'
                ELSE 'low'
            END as severity,
            r.trade_volume as current_vol,
            v.avg_volume as normal_vol,
            CASE WHEN v.avg_volume > 0 
                 THEN r.trade_volume / v.avg_volume 
                 ELSE 1 
            END as ratio,
            0::DECIMAL as price_chg,
            '거래량이 평소의 ' || ROUND(r.trade_volume / NULLIF(v.avg_volume, 0), 2) || '배 급증' as desc_text
        FROM recent_data r
        JOIN volume_baseline v ON r.code = v.code
        WHERE r.trade_volume > (v.avg_volume + (2 * sensitivity_multiplier) * COALESCE(v.volume_stddev, 0))
          AND v.avg_volume > 0
    ),
    price_anomalies AS (
        SELECT 
            'price_volatility' as anomaly_type,
            r.code,
            CASE 
                WHEN ABS(r.change_rate) > (15 * sensitivity_multiplier) THEN 'critical'
                WHEN ABS(r.change_rate) > (10 * sensitivity_multiplier) THEN 'high'
                WHEN ABS(r.change_rate) > (5 * sensitivity_multiplier) THEN 'medium'
                ELSE 'low'
            END as severity,
            0::DECIMAL as current_vol,
            0::DECIMAL as normal_vol,
            0::DECIMAL as ratio,
            ABS(r.change_rate) as price_chg,
            timeframe_hours || '시간간 ' || ROUND(ABS(r.change_rate), 2) || '% ' || 
            CASE WHEN r.change_rate > 0 THEN '급등' ELSE '급락' END as desc_text
        FROM recent_data r
        WHERE ABS(r.change_rate) > (5 * sensitivity_multiplier)
    )
    SELECT 
        a.anomaly_type,
        a.code,
        a.severity,
        a.current_vol,
        a.normal_vol,
        a.ratio,
        a.price_chg,
        a.desc_text
    FROM (
        SELECT * FROM volume_anomalies WHERE severity != 'low'
        UNION ALL
        SELECT * FROM price_anomalies WHERE severity != 'low'
    ) a
    ORDER BY 
        CASE a.severity 
            WHEN 'critical' THEN 1
            WHEN 'high' THEN 2
            WHEN 'medium' THEN 3
            ELSE 4
        END,
        a.code;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 편의 함수들 (LLM 질의를 위한)
-- =====================================================

-- 전체 시장 요약
CREATE OR REPLACE FUNCTION get_market_overview()
RETURNS TABLE (
    total_coins INTEGER,
    rising_coins INTEGER,
    falling_coins INTEGER,
    neutral_coins INTEGER,
    market_sentiment TEXT,
    top_gainer TEXT,
    top_loser TEXT,
    highest_volume TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH latest_data AS (
        SELECT DISTINCT ON (code)
            code, change_rate, acc_trade_volume_24h
        FROM ticker_data
        WHERE time >= NOW() - INTERVAL '1 hour'
        ORDER BY code, time DESC
    ),
    market_stats AS (
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE change_rate > 1) as rising,
            COUNT(*) FILTER (WHERE change_rate < -1) as falling,
            COUNT(*) FILTER (WHERE change_rate BETWEEN -1 AND 1) as neutral
        FROM latest_data
    ),
    extremes AS (
        SELECT 
            (SELECT code FROM latest_data ORDER BY change_rate DESC LIMIT 1) as top_gain,
            (SELECT code FROM latest_data ORDER BY change_rate ASC LIMIT 1) as top_loss,
            (SELECT code FROM latest_data ORDER BY acc_trade_volume_24h DESC LIMIT 1) as top_vol
        FROM latest_data LIMIT 1
    )
    SELECT 
        m.total,
        m.rising,
        m.falling,
        m.neutral,
        CASE 
            WHEN m.rising::float / m.total > 0.6 THEN 'bullish'
            WHEN m.falling::float / m.total > 0.6 THEN 'bearish'
            ELSE 'mixed'
        END,
        e.top_gain,
        e.top_loss,
        e.top_vol
    FROM market_stats m
    CROSS JOIN extremes e;
END;
$$ LANGUAGE plpgsql;

-- 함수 권한 설정
GRANT EXECUTE ON FUNCTION get_coin_summary(TEXT, INTEGER) TO PUBLIC;
GRANT EXECUTE ON FUNCTION get_market_movers(TEXT, INTEGER, INTEGER) TO PUBLIC;
GRANT EXECUTE ON FUNCTION detect_anomalies(INTEGER, INTEGER) TO PUBLIC;
GRANT EXECUTE ON FUNCTION get_market_overview() TO PUBLIC;

-- 사용 예시 주석
/*
-- 사용 예시:

-- 1. 비트코인 요약
SELECT * FROM get_coin_summary('KRW-BTC', 1);

-- 2. 상위 상승 코인 10개
SELECT * FROM get_market_movers('gainers', 10, 1);

-- 3. 이상 거래 탐지 (민감도 높음)
SELECT * FROM detect_anomalies(1, 4);

-- 4. 전체 시장 개요
SELECT * FROM get_market_overview();
*/