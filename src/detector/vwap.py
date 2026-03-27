"""VWAP (Volume Weighted Average Price) indicator."""

import pandas as pd

from src.detector.base import IndicatorBase, Signal

VWAP_SEVERITY = [
    (0.08, "critical"),
    (0.05, "high"),
    (0.03, "medium"),
    (0.02, "low"),
]


class VWAPIndicator(IndicatorBase):
    """VWAP — price deviation from volume-weighted average."""

    MIN_CANDLES = 10

    def __init__(self, weight: float = 0.25, window: int = 1440,
                 deviation_threshold: float = 0.02):
        super().__init__(name="vwap", weight=weight)
        self.window = window
        self.deviation_threshold = deviation_threshold

    def compute(self, coin_code: str, ohlcv_df: pd.DataFrame) -> Signal:
        df = self._filter_window(ohlcv_df, self.window)

        if len(df) < self.MIN_CANDLES:
            return self._not_ready(coin_code)

        total_volume = df["volume"].sum()

        if total_volume == 0:
            return Signal(
                indicator_name=self.name,
                coin_code=coin_code,
                value=0.0,
                is_anomaly=False,
                severity="skip",
                detail={"reason": "zero_volume"},
            )

        vwap = (df["close"] * df["volume"]).sum() / total_volume
        current_price = df["close"].iloc[-1]
        deviation_pct = (current_price - vwap) / vwap

        is_anomaly = bool(abs(deviation_pct) >= self.deviation_threshold)

        severity = "skip"
        if is_anomaly:
            abs_dev = abs(deviation_pct)
            for threshold, sev in VWAP_SEVERITY:
                if abs_dev >= threshold:
                    severity = sev
                    break
            else:
                severity = "low"

        return Signal(
            indicator_name=self.name,
            coin_code=coin_code,
            value=round(deviation_pct, 4),
            is_anomaly=is_anomaly,
            severity=severity,
            detail={
                "vwap_value": round(vwap, 2),
                "deviation_pct": round(deviation_pct, 4),
                "cumulative_volume": round(total_volume, 2),
                "current_price": current_price,
            },
        )
