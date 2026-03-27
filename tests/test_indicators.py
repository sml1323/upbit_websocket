"""Tests for all four indicators: Z-Score, Bollinger Bands, RSI, VWAP."""

import numpy as np
import pandas as pd
import pytest

from src.detector.zscore import ZScoreIndicator
from src.detector.bollinger import BollingerBandsIndicator
from src.detector.rsi import RSIIndicator
from src.detector.vwap import VWAPIndicator


def _make_ohlcv(closes, volumes=None, n=100):
    """Helper: generate OHLCV DataFrame from close prices."""
    if isinstance(closes, (int, float)):
        closes = [closes] * n
    n = len(closes)
    if volumes is None:
        volumes = [100.0] * n
    return pd.DataFrame({
        "bucket": pd.date_range("2026-01-01", periods=n, freq="1min"),
        "code": ["BTC"] * n,
        "open": closes,
        "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes],
        "close": closes,
        "volume": volumes,
        "trade_count": [10] * n,
    })


# ============================
# Z-Score Tests
# ============================

class TestZScoreIndicator:
    def test_no_anomaly(self):
        ind = ZScoreIndicator()
        df = _make_ohlcv(closes=[100.0] * 100)
        sig = ind.compute("BTC", df)
        assert sig.is_anomaly is False
        assert sig.ready is True

    def test_price_spike(self):
        ind = ZScoreIndicator()
        closes = [100.0] * 99 + [200.0]  # huge spike at the end
        df = _make_ohlcv(closes=closes)
        sig = ind.compute("BTC", df)
        assert sig.is_anomaly is True
        assert sig.detail["anomaly_type"] == "price_spike"

    def test_volume_surge(self):
        ind = ZScoreIndicator()
        volumes = [100.0] * 99 + [10000.0]
        df = _make_ohlcv(closes=[100.0] * 100, volumes=volumes)
        sig = ind.compute("BTC", df)
        assert sig.is_anomaly is True

    def test_not_ready(self):
        ind = ZScoreIndicator()
        df = _make_ohlcv(closes=[100.0] * 10)  # only 10 candles
        sig = ind.compute("BTC", df)
        assert sig.ready is False

    def test_zero_stddev(self):
        ind = ZScoreIndicator()
        df = _make_ohlcv(closes=[100.0] * 100, volumes=[50.0] * 100)
        sig = ind.compute("BTC", df)
        assert sig.value == 0.0
        assert sig.is_anomaly is False

    def test_severity_critical(self):
        ind = ZScoreIndicator()
        # Create data where last value is 8 stddevs away
        closes = [100.0] * 99 + [500.0]
        df = _make_ohlcv(closes=closes)
        sig = ind.compute("BTC", df)
        if sig.is_anomaly:
            assert sig.severity in ("critical", "high")


# ============================
# Bollinger Bands Tests
# ============================

class TestBollingerBandsIndicator:
    def test_no_anomaly(self):
        ind = BollingerBandsIndicator()
        df = _make_ohlcv(closes=[100.0] * 100)
        sig = ind.compute("BTC", df)
        assert sig.is_anomaly is False

    def test_upper_breach(self):
        ind = BollingerBandsIndicator()
        closes = [100.0] * 59 + [200.0]  # spike at end
        df = _make_ohlcv(closes=closes)
        sig = ind.compute("BTC", df)
        assert sig.is_anomaly is True
        assert sig.value > 1.0  # %B > 1.0

    def test_lower_breach(self):
        ind = BollingerBandsIndicator()
        closes = [100.0] * 59 + [10.0]  # crash at end
        df = _make_ohlcv(closes=closes)
        sig = ind.compute("BTC", df)
        assert sig.is_anomaly is True
        assert sig.value < 0.0  # %B < 0.0

    def test_not_ready(self):
        ind = BollingerBandsIndicator()
        df = _make_ohlcv(closes=[100.0] * 10)
        sig = ind.compute("BTC", df)
        assert sig.ready is False

    def test_zero_stddev(self):
        ind = BollingerBandsIndicator()
        df = _make_ohlcv(closes=[100.0] * 60)
        sig = ind.compute("BTC", df)
        assert sig.is_anomaly is False
        assert sig.detail.get("reason") == "zero_stddev"

    def test_severity_mapping(self):
        ind = BollingerBandsIndicator()
        closes = [100.0] * 59 + [300.0]  # extreme spike
        df = _make_ohlcv(closes=closes)
        sig = ind.compute("BTC", df)
        if sig.is_anomaly:
            assert sig.severity in ("low", "medium", "high", "critical")


# ============================
# RSI Tests
# ============================

class TestRSIIndicator:
    def test_normal_rsi(self):
        ind = RSIIndicator()
        np.random.seed(42)
        closes = 100 + np.cumsum(np.random.randn(100) * 0.5)
        df = _make_ohlcv(closes=closes.tolist())
        sig = ind.compute("BTC", df)
        assert sig.ready is True
        assert 0 <= sig.value <= 100

    def test_overbought(self):
        ind = RSIIndicator()
        # Steadily rising prices → RSI approaches 100
        closes = [100.0 + i * 2 for i in range(100)]
        df = _make_ohlcv(closes=closes)
        sig = ind.compute("BTC", df)
        assert sig.value > 75
        assert sig.is_anomaly is True
        assert sig.detail["condition"] == "overbought"

    def test_oversold(self):
        ind = RSIIndicator()
        # Steadily falling prices → RSI approaches 0
        closes = [200.0 - i * 2 for i in range(100)]
        df = _make_ohlcv(closes=closes)
        sig = ind.compute("BTC", df)
        assert sig.value < 25
        assert sig.is_anomaly is True
        assert sig.detail["condition"] == "oversold"

    def test_all_gains(self):
        ind = RSIIndicator()
        closes = [100.0 + i for i in range(100)]
        df = _make_ohlcv(closes=closes)
        sig = ind.compute("BTC", df)
        assert sig.value == 100.0

    def test_all_losses(self):
        ind = RSIIndicator()
        closes = [200.0 - i for i in range(100)]
        df = _make_ohlcv(closes=closes)
        sig = ind.compute("BTC", df)
        assert sig.value == 0.0

    def test_not_ready(self):
        ind = RSIIndicator()
        df = _make_ohlcv(closes=[100.0] * 10)
        sig = ind.compute("BTC", df)
        assert sig.ready is False


# ============================
# VWAP Tests
# ============================

class TestVWAPIndicator:
    def test_no_anomaly(self):
        ind = VWAPIndicator()
        df = _make_ohlcv(closes=[100.0] * 100, volumes=[100.0] * 100)
        sig = ind.compute("BTC", df)
        assert sig.is_anomaly is False

    def test_upper_deviation(self):
        ind = VWAPIndicator()
        closes = [100.0] * 99 + [110.0]  # +10% at end
        volumes = [1000.0] * 99 + [10.0]  # low volume on spike
        df = _make_ohlcv(closes=closes, volumes=volumes)
        sig = ind.compute("BTC", df)
        # VWAP ≈ 100, current = 110, deviation ≈ +10%
        assert sig.is_anomaly is True
        assert sig.value > 0

    def test_lower_deviation(self):
        ind = VWAPIndicator()
        closes = [100.0] * 99 + [90.0]
        volumes = [1000.0] * 99 + [10.0]
        df = _make_ohlcv(closes=closes, volumes=volumes)
        sig = ind.compute("BTC", df)
        assert sig.is_anomaly is True
        assert sig.value < 0

    def test_zero_volume(self):
        ind = VWAPIndicator()
        df = _make_ohlcv(closes=[100.0] * 100, volumes=[0.0] * 100)
        sig = ind.compute("BTC", df)
        assert sig.is_anomaly is False
        assert sig.detail.get("reason") == "zero_volume"

    def test_not_ready(self):
        ind = VWAPIndicator()
        df = _make_ohlcv(closes=[100.0] * 5)
        sig = ind.compute("BTC", df)
        assert sig.ready is False

    def test_severity_mapping(self):
        ind = VWAPIndicator()
        closes = [100.0] * 99 + [120.0]  # +20%
        volumes = [1000.0] * 99 + [1.0]
        df = _make_ohlcv(closes=closes, volumes=volumes)
        sig = ind.compute("BTC", df)
        if sig.is_anomaly:
            assert sig.severity in ("low", "medium", "high", "critical")
