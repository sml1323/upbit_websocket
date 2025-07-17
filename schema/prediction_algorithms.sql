-- =====================================================
-- Prediction Algorithms: Moving Average Crossover & Price Prediction
-- =====================================================

-- Function: calculate_moving_average_signals
-- 이동평균 크로스오버 기반 트렌드 분석 및 예측
CREATE OR REPLACE FUNCTION calculate_moving_average_signals(
    coin_code TEXT,
    short_period INTEGER DEFAULT 5,   -- 단기 이동평균 (5분)
    medium_period INTEGER DEFAULT 15, -- 중기 이동평균 (15분)
    long_period INTEGER DEFAULT 60    -- 장기 이동평균 (1시간)
)
RETURNS TABLE (
    code TEXT,
    "time" TIMESTAMPTZ,
    price DECIMAL,
    ma_short DECIMAL,
    ma_medium DECIMAL,
    ma_long DECIMAL,
    crossover_signal TEXT,
    trend_strength TEXT,
    price_prediction_5m DECIMAL,
    prediction_confidence INTEGER
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
          AND t.time >= NOW() - INTERVAL '12 hours'
        ORDER BY t.time
    ),
    moving_averages AS (
        SELECT 
            pd.code,
            pd.time,
            pd.trade_price,
            AVG(pd.trade_price) OVER (ORDER BY pd.time ROWS BETWEEN short_period-1 PRECEDING AND CURRENT ROW) as ma_short_val,
            AVG(pd.trade_price) OVER (ORDER BY pd.time ROWS BETWEEN medium_period-1 PRECEDING AND CURRENT ROW) as ma_medium_val,
            AVG(pd.trade_price) OVER (ORDER BY pd.time ROWS BETWEEN long_period-1 PRECEDING AND CURRENT ROW) as ma_long_val,
            ROW_NUMBER() OVER (ORDER BY pd.time) as row_num
        FROM price_data pd
    ),
    ma_with_lag AS (
        SELECT 
            ma.*,
            LAG(ma.ma_short_val) OVER (ORDER BY ma.time) as prev_ma_short,
            LAG(ma.ma_medium_val) OVER (ORDER BY ma.time) as prev_ma_medium
        FROM moving_averages ma
    ),
    crossover_analysis AS (
        SELECT 
            ma.code,
            ma.time,
            ma.trade_price,
            ma.ma_short_val,
            ma.ma_medium_val,
            ma.ma_long_val,
            CASE 
                WHEN ma.ma_short_val > ma.ma_medium_val AND ma.prev_ma_short <= ma.prev_ma_medium THEN 'golden_cross'
                WHEN ma.ma_short_val < ma.ma_medium_val AND ma.prev_ma_short >= ma.prev_ma_medium THEN 'death_cross'
                WHEN ma.ma_short_val > ma.ma_medium_val AND ma.ma_medium_val > ma.ma_long_val THEN 'strong_bullish'
                WHEN ma.ma_short_val < ma.ma_medium_val AND ma.ma_medium_val < ma.ma_long_val THEN 'strong_bearish'
                WHEN ma.ma_short_val > ma.ma_medium_val THEN 'bullish'
                WHEN ma.ma_short_val < ma.ma_medium_val THEN 'bearish'
                ELSE 'neutral'
            END as crossover_sig,
            CASE 
                WHEN ABS(ma.ma_short_val - ma.ma_medium_val) / ma.ma_medium_val > 0.02 THEN 'very_strong'
                WHEN ABS(ma.ma_short_val - ma.ma_medium_val) / ma.ma_medium_val > 0.01 THEN 'strong'
                WHEN ABS(ma.ma_short_val - ma.ma_medium_val) / ma.ma_medium_val > 0.005 THEN 'moderate'
                ELSE 'weak'
            END as strength
        FROM ma_with_lag ma
        WHERE ma.row_num >= long_period
    ),
    price_prediction AS (
        SELECT 
            ca.*,
            CASE 
                WHEN ca.crossover_sig IN ('golden_cross', 'strong_bullish') THEN 
                    ca.trade_price + (ca.ma_short_val - ca.ma_medium_val) * 2
                WHEN ca.crossover_sig IN ('death_cross', 'strong_bearish') THEN 
                    ca.trade_price - ABS(ca.ma_short_val - ca.ma_medium_val) * 2
                WHEN ca.crossover_sig = 'bullish' THEN 
                    ca.trade_price + (ca.ma_short_val - ca.ma_medium_val) * 1.5
                WHEN ca.crossover_sig = 'bearish' THEN 
                    ca.trade_price - ABS(ca.ma_short_val - ca.ma_medium_val) * 1.5
                ELSE ca.trade_price
            END as predicted_price,
            CASE 
                WHEN ca.crossover_sig IN ('golden_cross', 'death_cross') THEN 85
                WHEN ca.crossover_sig IN ('strong_bullish', 'strong_bearish') THEN 75
                WHEN ca.strength IN ('very_strong', 'strong') THEN 70
                WHEN ca.strength = 'moderate' THEN 60
                ELSE 40
            END as confidence
        FROM crossover_analysis ca
    )
    SELECT 
        pp.code,
        pp.time,
        pp.trade_price,
        ROUND(pp.ma_short_val, 2),
        ROUND(pp.ma_medium_val, 2),
        ROUND(pp.ma_long_val, 2),
        pp.crossover_sig,
        pp.strength,
        ROUND(pp.predicted_price, 2),
        pp.confidence
    FROM price_prediction pp
    ORDER BY pp.time DESC
    LIMIT 100;
END;
$$ LANGUAGE plpgsql;

-- Function: detect_rsi_divergence
-- RSI 다이버전스 탐지 (가격과 RSI 간의 괴리 분석)
CREATE OR REPLACE FUNCTION detect_rsi_divergence(
    coin_code TEXT,
    lookback_periods INTEGER DEFAULT 20
)
RETURNS TABLE (
    code TEXT,
    "time" TIMESTAMPTZ,
    price DECIMAL,
    rsi DECIMAL,
    divergence_type TEXT,
    strength TEXT,
    prediction_signal TEXT,
    confidence_score INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH rsi_data AS (
        SELECT 
            r.code,
            r.time,
            r.price,
            r.rsi
        FROM calculate_rsi(coin_code, 14) r
        ORDER BY r.time DESC
        LIMIT lookback_periods
    ),
    price_peaks AS (
        SELECT 
            rd.*,
            LAG(rd.price, 1) OVER (ORDER BY rd.time) as prev_price,
            LEAD(rd.price, 1) OVER (ORDER BY rd.time) as next_price,
            LAG(rd.rsi, 1) OVER (ORDER BY rd.time) as prev_rsi,
            LEAD(rd.rsi, 1) OVER (ORDER BY rd.time) as next_rsi
        FROM rsi_data rd
    ),
    peaks_valleys AS (
        SELECT 
            pp.*,
            CASE 
                WHEN pp.price > pp.prev_price AND pp.price > pp.next_price THEN 'price_peak'
                WHEN pp.price < pp.prev_price AND pp.price < pp.next_price THEN 'price_valley'
                ELSE 'normal'
            END as price_pattern,
            CASE 
                WHEN pp.rsi > pp.prev_rsi AND pp.rsi > pp.next_rsi THEN 'rsi_peak'
                WHEN pp.rsi < pp.prev_rsi AND pp.rsi < pp.next_rsi THEN 'rsi_valley'
                ELSE 'normal'
            END as rsi_pattern
        FROM price_peaks pp
        WHERE pp.prev_price IS NOT NULL AND pp.next_price IS NOT NULL
    ),
    divergence_detection AS (
        SELECT 
            pv.*,
            CASE 
                WHEN pv.price_pattern = 'price_peak' AND pv.rsi_pattern = 'rsi_valley' THEN 'bearish_divergence'
                WHEN pv.price_pattern = 'price_valley' AND pv.rsi_pattern = 'rsi_peak' THEN 'bullish_divergence'
                WHEN pv.price_pattern = 'price_peak' AND pv.rsi_pattern = 'rsi_peak' 
                     AND pv.rsi < 50 THEN 'hidden_bearish'
                WHEN pv.price_pattern = 'price_valley' AND pv.rsi_pattern = 'rsi_valley' 
                     AND pv.rsi > 50 THEN 'hidden_bullish'
                ELSE 'no_divergence'
            END as divergence,
            CASE 
                WHEN ABS(pv.rsi - 50) > 30 THEN 'strong'
                WHEN ABS(pv.rsi - 50) > 20 THEN 'moderate'
                ELSE 'weak'
            END as div_strength
        FROM peaks_valleys pv
    )
    SELECT 
        dd.code,
        dd.time,
        dd.price,
        dd.rsi,
        dd.divergence,
        dd.div_strength,
        CASE 
            WHEN dd.divergence = 'bullish_divergence' THEN 'strong_buy'
            WHEN dd.divergence = 'bearish_divergence' THEN 'strong_sell'
            WHEN dd.divergence = 'hidden_bullish' THEN 'buy'
            WHEN dd.divergence = 'hidden_bearish' THEN 'sell'
            ELSE 'hold'
        END,
        CASE 
            WHEN dd.divergence IN ('bullish_divergence', 'bearish_divergence') AND dd.div_strength = 'strong' THEN 90
            WHEN dd.divergence IN ('bullish_divergence', 'bearish_divergence') AND dd.div_strength = 'moderate' THEN 75
            WHEN dd.divergence LIKE 'hidden_%' AND dd.div_strength = 'strong' THEN 70
            WHEN dd.divergence LIKE 'hidden_%' AND dd.div_strength = 'moderate' THEN 60
            ELSE 30
        END
    FROM divergence_detection dd
    WHERE dd.divergence != 'no_divergence'
    ORDER BY dd.time DESC;
END;
$$ LANGUAGE plpgsql;

-- Function: predict_bollinger_breakout
-- 볼린저밴드 브레이크아웃 예측
CREATE OR REPLACE FUNCTION predict_bollinger_breakout(
    coin_code TEXT,
    squeeze_threshold DECIMAL DEFAULT 0.02  -- 2% 스퀴즈 임계값
)
RETURNS TABLE (
    code TEXT,
    "time" TIMESTAMPTZ,
    price DECIMAL,
    band_width DECIMAL,
    is_squeeze BOOLEAN,
    breakout_probability INTEGER,
    predicted_direction TEXT,
    target_price DECIMAL,
    confidence_score INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH bb_data AS (
        SELECT 
            b.code,
            b.time,
            b.price,
            b.middle_band,
            b.upper_band,
            b.lower_band,
            b.band_width,
            b.position_pct,
            b.squeeze
        FROM calculate_bollinger_bands(coin_code, 20, 2.0) b
        ORDER BY b.time DESC
        LIMIT 50
    ),
    volume_data AS (
        SELECT 
            t.time,
            t.acc_trade_volume,
            AVG(t.acc_trade_volume) OVER (ORDER BY t.time ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as avg_volume
        FROM ticker_data t
        WHERE t.code = coin_code
          AND t.time >= NOW() - INTERVAL '6 hours'
        ORDER BY t.time DESC
        LIMIT 50
    ),
    breakout_analysis AS (
        SELECT 
            bb.*,
            vd.acc_trade_volume,
            vd.avg_volume,
            LAG(bb.squeeze, 1) OVER (ORDER BY bb.time) as prev_squeeze,
            LAG(bb.band_width, 1) OVER (ORDER BY bb.time) as prev_band_width,
            CASE 
                WHEN bb.band_width < (bb.middle_band * squeeze_threshold) THEN TRUE
                ELSE FALSE
            END as is_tight_squeeze
        FROM bb_data bb
        LEFT JOIN volume_data vd ON bb.time = vd.time
    ),
    breakout_prediction AS (
        SELECT 
            ba.*,
            CASE 
                WHEN ba.is_tight_squeeze AND ba.acc_trade_volume > ba.avg_volume * 1.5 THEN 80
                WHEN ba.is_tight_squeeze AND ba.acc_trade_volume > ba.avg_volume * 1.2 THEN 65
                WHEN ba.is_tight_squeeze THEN 50
                WHEN ba.squeeze AND NOT ba.prev_squeeze THEN 40
                ELSE 20
            END as breakout_prob,
            CASE 
                WHEN ba.position_pct > 70 THEN 'upward'
                WHEN ba.position_pct < 30 THEN 'downward'
                WHEN ba.price > ba.middle_band THEN 'upward'
                ELSE 'downward'
            END as direction,
            CASE 
                WHEN ba.position_pct > 70 THEN ba.upper_band + (ba.band_width * 0.5)
                WHEN ba.position_pct < 30 THEN ba.lower_band - (ba.band_width * 0.5)
                WHEN ba.price > ba.middle_band THEN ba.upper_band
                ELSE ba.lower_band
            END as target
        FROM breakout_analysis ba
    )
    SELECT 
        bp.code,
        bp.time,
        bp.price,
        ROUND(bp.band_width, 2),
        bp.is_tight_squeeze,
        bp.breakout_prob,
        bp.direction,
        ROUND(bp.target, 2),
        CASE 
            WHEN bp.breakout_prob > 70 AND bp.acc_trade_volume > bp.avg_volume * 1.5 THEN 85
            WHEN bp.breakout_prob > 60 AND bp.acc_trade_volume > bp.avg_volume * 1.2 THEN 75
            WHEN bp.breakout_prob > 50 THEN 65
            ELSE 45
        END
    FROM breakout_prediction bp
    ORDER BY bp.time DESC;
END;
$$ LANGUAGE plpgsql;

-- Function: analyze_volume_confirmation
-- 거래량 확인 신호 분석
CREATE OR REPLACE FUNCTION analyze_volume_confirmation(
    coin_code TEXT,
    volume_threshold_multiplier DECIMAL DEFAULT 1.5
)
RETURNS TABLE (
    code TEXT,
    "time" TIMESTAMPTZ,
    price DECIMAL,
    volume DECIMAL,
    avg_volume DECIMAL,
    volume_ratio DECIMAL,
    price_change_pct DECIMAL,
    volume_signal TEXT,
    confirmation_strength TEXT,
    reliability_score INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH volume_data AS (
        SELECT 
            t.code,
            t.time,
            t.trade_price,
            t.acc_trade_volume,
            t.change_rate,
            AVG(t.acc_trade_volume) OVER (ORDER BY t.time ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as avg_vol,
            LAG(t.trade_price, 1) OVER (ORDER BY t.time) as prev_price
        FROM ticker_data t
        WHERE t.code = coin_code
          AND t.time >= NOW() - INTERVAL '6 hours'
        ORDER BY t.time
    ),
    volume_analysis AS (
        SELECT 
            vd.*,
            vd.acc_trade_volume / vd.avg_vol as vol_ratio,
            CASE 
                WHEN vd.prev_price IS NOT NULL THEN 
                    ((vd.trade_price - vd.prev_price) / vd.prev_price) * 100
                ELSE 0
            END as price_chg_pct
        FROM volume_data vd
        WHERE vd.avg_vol > 0
    ),
    volume_signals AS (
        SELECT 
            va.*,
            CASE 
                WHEN va.vol_ratio > volume_threshold_multiplier * 2 AND va.price_chg_pct > 2 THEN 'strong_bullish_breakout'
                WHEN va.vol_ratio > volume_threshold_multiplier * 2 AND va.price_chg_pct < -2 THEN 'strong_bearish_breakdown'
                WHEN va.vol_ratio > volume_threshold_multiplier AND va.price_chg_pct > 1 THEN 'bullish_confirmation'
                WHEN va.vol_ratio > volume_threshold_multiplier AND va.price_chg_pct < -1 THEN 'bearish_confirmation'
                WHEN va.vol_ratio > volume_threshold_multiplier THEN 'volume_spike'
                WHEN va.vol_ratio < 0.5 THEN 'low_volume_warning'
                ELSE 'normal'
            END as vol_signal,
            CASE 
                WHEN va.vol_ratio > 3 THEN 'very_strong'
                WHEN va.vol_ratio > 2 THEN 'strong'
                WHEN va.vol_ratio > 1.5 THEN 'moderate'
                WHEN va.vol_ratio > 1 THEN 'weak'
                ELSE 'very_weak'
            END as confirmation_str
        FROM volume_analysis va
    )
    SELECT 
        vs.code,
        vs.time,
        vs.trade_price,
        ROUND(vs.acc_trade_volume, 2),
        ROUND(vs.avg_vol, 2),
        ROUND(vs.vol_ratio, 2),
        ROUND(vs.price_chg_pct, 2),
        vs.vol_signal,
        vs.confirmation_str,
        CASE 
            WHEN vs.vol_signal LIKE 'strong_%' AND vs.confirmation_str = 'very_strong' THEN 95
            WHEN vs.vol_signal LIKE 'strong_%' AND vs.confirmation_str = 'strong' THEN 85
            WHEN vs.vol_signal LIKE '%confirmation' AND vs.confirmation_str IN ('very_strong', 'strong') THEN 80
            WHEN vs.vol_signal LIKE '%confirmation' AND vs.confirmation_str = 'moderate' THEN 70
            WHEN vs.vol_signal = 'volume_spike' THEN 60
            WHEN vs.vol_signal = 'low_volume_warning' THEN 25
            ELSE 50
        END
    FROM volume_signals vs
    ORDER BY vs.time DESC
    LIMIT 100;
END;
$$ LANGUAGE plpgsql;

-- Function: get_comprehensive_prediction
-- 통합 예측 모델 (모든 지표 결합)
CREATE OR REPLACE FUNCTION get_comprehensive_prediction(
    coin_code TEXT,
    prediction_timeframe INTEGER DEFAULT 5  -- minutes
)
RETURNS TABLE (
    code TEXT,
    current_price DECIMAL,
    predicted_price_5m DECIMAL,
    predicted_price_15m DECIMAL,
    predicted_price_1h DECIMAL,
    overall_signal TEXT,
    confidence_score INTEGER,
    risk_level TEXT,
    key_factors TEXT[],
    recommendation TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH current_data AS (
        SELECT DISTINCT ON (t.code)
            t.code,
            t.trade_price,
            t.time
        FROM ticker_data t
        WHERE t.code = coin_code
        ORDER BY t.code, t.time DESC
        LIMIT 1
    ),
    ma_signals AS (
        SELECT 
            crossover_signal,
            trend_strength,
            price_prediction_5m,
            prediction_confidence
        FROM calculate_moving_average_signals(coin_code, 5, 15, 60)
        ORDER BY time DESC
        LIMIT 1
    ),
    rsi_div AS (
        SELECT 
            divergence_type,
            prediction_signal as rsi_signal,
            d.confidence_score as rsi_confidence
        FROM detect_rsi_divergence(coin_code, 20) d
        ORDER BY d.time DESC
        LIMIT 1
    ),
    bb_breakout AS (
        SELECT 
            breakout_probability,
            predicted_direction,
            target_price,
            b.confidence_score as bb_confidence
        FROM predict_bollinger_breakout(coin_code, 0.02) b
        ORDER BY b.time DESC
        LIMIT 1
    ),
    volume_conf AS (
        SELECT 
            volume_signal,
            confirmation_strength,
            reliability_score
        FROM analyze_volume_confirmation(coin_code, 1.5)
        ORDER BY time DESC
        LIMIT 1
    ),
    combined_prediction AS (
        SELECT 
            cd.code,
            cd.trade_price,
            COALESCE(ms.price_prediction_5m, cd.trade_price) as pred_5m,
            CASE 
                WHEN ms.crossover_signal IN ('golden_cross', 'strong_bullish') THEN 
                    cd.trade_price * 1.02
                WHEN ms.crossover_signal IN ('death_cross', 'strong_bearish') THEN 
                    cd.trade_price * 0.98
                ELSE cd.trade_price * 1.005
            END as pred_15m,
            CASE 
                WHEN bb.predicted_direction = 'upward' AND bb.breakout_probability > 70 THEN 
                    bb.target_price
                WHEN bb.predicted_direction = 'downward' AND bb.breakout_probability > 70 THEN 
                    bb.target_price
                ELSE cd.trade_price
            END as pred_1h,
            -- 통합 신호 계산
            CASE 
                WHEN ms.crossover_signal IN ('golden_cross', 'strong_bullish') 
                     AND COALESCE(rd.rsi_signal, 'hold') IN ('strong_buy', 'buy')
                     AND COALESCE(vc.volume_signal, 'normal') LIKE '%bullish%' THEN 'strong_buy'
                WHEN ms.crossover_signal IN ('death_cross', 'strong_bearish') 
                     AND COALESCE(rd.rsi_signal, 'hold') IN ('strong_sell', 'sell')
                     AND COALESCE(vc.volume_signal, 'normal') LIKE '%bearish%' THEN 'strong_sell'
                WHEN ms.crossover_signal = 'bullish' 
                     AND COALESCE(bb.predicted_direction, 'neutral') = 'upward' THEN 'buy'
                WHEN ms.crossover_signal = 'bearish' 
                     AND COALESCE(bb.predicted_direction, 'neutral') = 'downward' THEN 'sell'
                ELSE 'hold'
            END as overall_sig,
            -- 신뢰도 점수 계산
            (COALESCE(ms.prediction_confidence, 40) + 
             COALESCE(rd.rsi_confidence, 40) + 
             COALESCE(bb.bb_confidence, 40) + 
             COALESCE(vc.reliability_score, 40)) / 4 as avg_confidence
        FROM current_data cd
        LEFT JOIN ma_signals ms ON TRUE
        LEFT JOIN rsi_div rd ON TRUE  
        LEFT JOIN bb_breakout bb ON TRUE
        LEFT JOIN volume_conf vc ON TRUE
    )
    SELECT 
        cp.code,
        cp.trade_price,
        ROUND(cp.pred_5m, 2),
        ROUND(cp.pred_15m, 2),
        ROUND(cp.pred_1h, 2),
        cp.overall_sig,
        cp.avg_confidence::INTEGER,
        CASE 
            WHEN cp.avg_confidence > 80 THEN 'low'
            WHEN cp.avg_confidence > 60 THEN 'medium'
            ELSE 'high'
        END,
        ARRAY[
            COALESCE('MA: ' || ms.crossover_signal, 'MA: neutral'),
            COALESCE('RSI: ' || rd.divergence_type, 'RSI: normal'),
            COALESCE('BB: ' || bb.predicted_direction, 'BB: neutral'),
            COALESCE('Volume: ' || vc.volume_signal, 'Volume: normal')
        ],
        CASE 
            WHEN cp.overall_sig = 'strong_buy' THEN 'Strong Buy - Multiple confirming signals'
            WHEN cp.overall_sig = 'strong_sell' THEN 'Strong Sell - Multiple confirming signals'
            WHEN cp.overall_sig = 'buy' THEN 'Buy - Positive trend indicators'
            WHEN cp.overall_sig = 'sell' THEN 'Sell - Negative trend indicators'
            ELSE 'Hold - Mixed or neutral signals'
        END
    FROM combined_prediction cp
    LEFT JOIN ma_signals ms ON TRUE
    LEFT JOIN rsi_div rd ON TRUE
    LEFT JOIN bb_breakout bb ON TRUE
    LEFT JOIN volume_conf vc ON TRUE;
END;
$$ LANGUAGE plpgsql;

-- 함수 권한 설정
GRANT EXECUTE ON FUNCTION calculate_moving_average_signals(TEXT, INTEGER, INTEGER, INTEGER) TO PUBLIC;
GRANT EXECUTE ON FUNCTION detect_rsi_divergence(TEXT, INTEGER) TO PUBLIC;
GRANT EXECUTE ON FUNCTION predict_bollinger_breakout(TEXT, DECIMAL) TO PUBLIC;
GRANT EXECUTE ON FUNCTION analyze_volume_confirmation(TEXT, DECIMAL) TO PUBLIC;
GRANT EXECUTE ON FUNCTION get_comprehensive_prediction(TEXT, INTEGER) TO PUBLIC;

-- 사용 예시 주석
/*
-- 사용 예시:

-- 1. 이동평균 신호 및 예측
SELECT * FROM calculate_moving_average_signals('KRW-BTC', 5, 15, 60) ORDER BY time DESC LIMIT 5;

-- 2. RSI 다이버전스 탐지
SELECT * FROM detect_rsi_divergence('KRW-BTC', 20) ORDER BY time DESC LIMIT 5;

-- 3. 볼린저밴드 브레이크아웃 예측
SELECT * FROM predict_bollinger_breakout('KRW-BTC', 0.02) ORDER BY time DESC LIMIT 5;

-- 4. 거래량 확인 신호
SELECT * FROM analyze_volume_confirmation('KRW-BTC', 1.5) ORDER BY time DESC LIMIT 5;

-- 5. 통합 예측 모델
SELECT * FROM get_comprehensive_prediction('KRW-BTC', 5);
*/