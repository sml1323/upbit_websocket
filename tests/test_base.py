"""Tests for indicator base classes and registry."""

import pandas as pd

from src.detector.base import IndicatorBase, IndicatorRegistry, Signal


class DummyIndicator(IndicatorBase):
    def compute(self, coin_code, ohlcv_df):
        return Signal(
            indicator_name=self.name,
            coin_code=coin_code,
            value=1.0,
            is_anomaly=True,
            severity="low",
            detail={},
        )


class TestIndicatorBase:
    def test_init(self):
        ind = DummyIndicator(name="test", weight=0.5)
        assert ind.name == "test"
        assert ind.weight == 0.5

    def test_not_ready(self):
        ind = DummyIndicator(name="test", weight=1.0)
        sig = ind._not_ready("BTC")
        assert sig.ready is False
        assert sig.is_anomaly is False
        assert sig.severity == "skip"
        assert sig.coin_code == "BTC"

    def test_filter_window(self):
        ind = DummyIndicator(name="test", weight=1.0)
        df = pd.DataFrame({
            "bucket": pd.date_range("2026-01-01", periods=100, freq="1min"),
            "close": range(100),
        })
        filtered = ind._filter_window(df, 10)
        assert len(filtered) == 10
        assert filtered["close"].iloc[-1] == 99

    def test_filter_window_empty(self):
        ind = DummyIndicator(name="test", weight=1.0)
        df = pd.DataFrame(columns=["bucket", "close"])
        filtered = ind._filter_window(df, 10)
        assert len(filtered) == 0


class TestIndicatorRegistry:
    def test_register_and_get_all(self):
        registry = IndicatorRegistry()
        ind1 = DummyIndicator(name="a", weight=0.5)
        ind2 = DummyIndicator(name="b", weight=0.5)
        registry.register(ind1)
        registry.register(ind2)
        assert len(registry.get_all()) == 2

    def test_get_by_name(self):
        registry = IndicatorRegistry()
        ind = DummyIndicator(name="test", weight=1.0)
        registry.register(ind)
        assert registry.get_by_name("test") is ind
        assert registry.get_by_name("nonexistent") is None

    def test_register_overwrites(self):
        registry = IndicatorRegistry()
        ind1 = DummyIndicator(name="test", weight=0.3)
        ind2 = DummyIndicator(name="test", weight=0.7)
        registry.register(ind1)
        registry.register(ind2)
        assert len(registry.get_all()) == 1
        assert registry.get_by_name("test").weight == 0.7
