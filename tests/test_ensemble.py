"""Tests for EnsembleScorer."""

import pandas as pd
import pytest

from src.detector.base import IndicatorBase, IndicatorRegistry, Signal, EnsembleResult
from src.detector.ensemble import EnsembleScorer, _compute_severity


class FakeIndicator(IndicatorBase):
    """Test helper: configurable indicator."""

    def __init__(self, name, weight, is_anomaly=False, ready=True, raises=False):
        super().__init__(name=name, weight=weight)
        self._is_anomaly = is_anomaly
        self._ready = ready
        self._raises = raises

    def compute(self, coin_code, ohlcv_df):
        if self._raises:
            raise ValueError("intentional error")
        return Signal(
            indicator_name=self.name,
            coin_code=coin_code,
            value=5.0 if self._is_anomaly else 1.0,
            is_anomaly=self._is_anomaly,
            severity="high" if self._is_anomaly else "skip",
            detail={"test": True},
            ready=self._ready,
        )


def _empty_df():
    return pd.DataFrame(columns=["bucket", "code", "close", "volume"])


class TestComputeSeverity:
    def test_one_firing(self):
        assert _compute_severity(1) == "low"

    def test_two_firing(self):
        assert _compute_severity(2) == "medium"

    def test_three_firing(self):
        assert _compute_severity(3) == "high"

    def test_four_firing(self):
        assert _compute_severity(4) == "critical"


class TestEnsembleScorer:
    def test_all_normal(self):
        registry = IndicatorRegistry()
        registry.register(FakeIndicator("a", 0.5, is_anomaly=False))
        registry.register(FakeIndicator("b", 0.5, is_anomaly=False))
        scorer = EnsembleScorer(registry)
        result = scorer.score("BTC", _empty_df())
        assert result.is_anomaly is False
        assert result.ensemble_score == 0.0
        assert result.firing_count == 0

    def test_all_anomaly(self):
        registry = IndicatorRegistry()
        registry.register(FakeIndicator("a", 0.5, is_anomaly=True))
        registry.register(FakeIndicator("b", 0.5, is_anomaly=True))
        scorer = EnsembleScorer(registry)
        result = scorer.score("BTC", _empty_df())
        assert result.is_anomaly is True
        assert result.ensemble_score == 1.0
        assert result.firing_count == 2

    def test_single_indicator_fires(self):
        registry = IndicatorRegistry()
        registry.register(FakeIndicator("a", 0.3, is_anomaly=True))
        registry.register(FakeIndicator("b", 0.7, is_anomaly=False))
        scorer = EnsembleScorer(registry)
        result = scorer.score("BTC", _empty_df())
        # weighted_sum = 0.3/1.0 = 0.3 < 0.5 → not anomaly
        assert result.is_anomaly is False
        assert result.firing_count == 1

    def test_weighted_threshold(self):
        registry = IndicatorRegistry()
        registry.register(FakeIndicator("a", 0.6, is_anomaly=True))
        registry.register(FakeIndicator("b", 0.4, is_anomaly=False))
        scorer = EnsembleScorer(registry)
        result = scorer.score("BTC", _empty_df())
        # weighted_sum = 0.6/1.0 = 0.6 >= 0.5 → anomaly
        assert result.is_anomaly is True

    def test_partial_ready(self):
        registry = IndicatorRegistry()
        registry.register(FakeIndicator("a", 0.5, is_anomaly=True, ready=True))
        registry.register(FakeIndicator("b", 0.5, is_anomaly=False, ready=False))
        scorer = EnsembleScorer(registry)
        result = scorer.score("BTC", _empty_df())
        # Only 'a' is active, weight_sum = 0.5, normalized = 0.5/0.5 = 1.0
        assert result.is_anomaly is True
        assert result.active_indicator_count == 1

    def test_all_not_ready(self):
        registry = IndicatorRegistry()
        registry.register(FakeIndicator("a", 0.5, ready=False))
        registry.register(FakeIndicator("b", 0.5, ready=False))
        scorer = EnsembleScorer(registry)
        result = scorer.score("BTC", _empty_df())
        assert result.is_anomaly is False
        assert result.active_indicator_count == 0
        assert result.severity == "skip"

    def test_exception_isolation(self):
        registry = IndicatorRegistry()
        registry.register(FakeIndicator("good", 0.5, is_anomaly=True))
        registry.register(FakeIndicator("bad", 0.5, raises=True))
        scorer = EnsembleScorer(registry)
        result = scorer.score("BTC", _empty_df())
        # 'bad' caught as not ready, 'good' fires alone
        assert result.active_indicator_count == 1
        assert result.is_anomaly is True

    def test_severity_by_firing_count(self):
        registry = IndicatorRegistry()
        for i in range(4):
            registry.register(FakeIndicator(f"ind{i}", 0.25, is_anomaly=True))
        scorer = EnsembleScorer(registry)
        result = scorer.score("BTC", _empty_df())
        assert result.severity == "critical"
        assert result.firing_count == 4

    def test_signals_include_all(self):
        registry = IndicatorRegistry()
        registry.register(FakeIndicator("a", 0.5, is_anomaly=True))
        registry.register(FakeIndicator("b", 0.5, is_anomaly=False, ready=False))
        scorer = EnsembleScorer(registry)
        result = scorer.score("BTC", _empty_df())
        assert len(result.signals) == 2
        names = {s.indicator_name for s in result.signals}
        assert names == {"a", "b"}
