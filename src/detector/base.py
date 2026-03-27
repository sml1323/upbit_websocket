"""Indicator base classes and registry for ensemble anomaly detection."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src.config import setup_logging

logger = setup_logging("indicator-base")


@dataclass
class Signal:
    """Individual indicator output."""
    indicator_name: str
    coin_code: str
    value: float
    is_anomaly: bool
    severity: str       # low / medium / high / critical / skip
    detail: dict
    ready: bool = True  # False if insufficient data


@dataclass
class EnsembleResult:
    """Combined output from all indicators for one coin."""
    coin_code: str
    is_anomaly: bool
    ensemble_score: float         # 0.0 ~ 1.0
    firing_count: int
    signals: list[Signal]
    severity: str                 # low / medium / high / critical
    active_indicator_count: int   # ready=True indicators


class IndicatorBase(ABC):
    """Abstract base for all anomaly indicators."""

    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight

    @abstractmethod
    def compute(self, coin_code: str, ohlcv_df: pd.DataFrame) -> Signal:
        """Compute signal from pre-fetched OHLCV DataFrame.

        Must return Signal(ready=False) when data is insufficient.
        """
        ...

    def _filter_window(self, ohlcv_df: pd.DataFrame, minutes: int) -> pd.DataFrame:
        """Filter DataFrame to the most recent N minutes. Shared helper."""
        if ohlcv_df.empty:
            return ohlcv_df
        sorted_df = ohlcv_df.sort_values("bucket", ascending=True)
        return sorted_df.tail(minutes)

    def _not_ready(self, coin_code: str) -> Signal:
        """Convenience: return a not-ready signal."""
        return Signal(
            indicator_name=self.name,
            coin_code=coin_code,
            value=0.0,
            is_anomaly=False,
            severity="skip",
            detail={},
            ready=False,
        )


class IndicatorRegistry:
    """Registry for indicator plugins."""

    def __init__(self):
        self._indicators: dict[str, IndicatorBase] = {}

    def register(self, indicator: IndicatorBase) -> None:
        self._indicators[indicator.name] = indicator

    def get_all(self) -> list[IndicatorBase]:
        return list(self._indicators.values())

    def get_by_name(self, name: str) -> Optional[IndicatorBase]:
        return self._indicators.get(name)
