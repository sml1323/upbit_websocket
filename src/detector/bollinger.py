"""Bollinger Bands indicator."""

import pandas as pd

from src.detector.base import IndicatorBase, Signal


class BollingerBandsIndicator(IndicatorBase):
    """Bollinger Bands — %B based anomaly detection."""

    MIN_CANDLES = 60

    def __init__(self, weight: float = 0.25, window: int = 60, num_std: float = 2.0):
        super().__init__(name="bollinger_bands", weight=weight)
        self.window = window
        self.num_std = num_std

    def compute(self, coin_code: str, ohlcv_df: pd.DataFrame) -> Signal:
        df = self._filter_window(ohlcv_df, self.window)

        if len(df) < self.MIN_CANDLES:
            return self._not_ready(coin_code)

        closes = df["close"]
        ma = closes.mean()
        std = closes.std()

        if std == 0:
            return Signal(
                indicator_name=self.name,
                coin_code=coin_code,
                value=0.5,
                is_anomaly=False,
                severity="skip",
                detail={"reason": "zero_stddev"},
            )

        upper_band = ma + self.num_std * std
        lower_band = ma - self.num_std * std
        current_price = closes.iloc[-1]
        bandwidth = (upper_band - lower_band) / ma
        percent_b = (current_price - lower_band) / (upper_band - lower_band)

        # Anomaly: price outside bands (%B > 1.0 or < 0.0)
        is_anomaly = bool(percent_b > 1.0 or percent_b < 0.0)

        severity = "skip"
        if is_anomaly:
            deviation = max(percent_b - 1.0, -percent_b)
            if deviation >= 0.4:
                severity = "critical"
            elif deviation >= 0.2:
                severity = "high"
            elif deviation >= 0.1:
                severity = "medium"
            else:
                severity = "low"

        return Signal(
            indicator_name=self.name,
            coin_code=coin_code,
            value=round(percent_b, 4),
            is_anomaly=is_anomaly,
            severity=severity,
            detail={
                "upper_band": round(upper_band, 2),
                "lower_band": round(lower_band, 2),
                "bandwidth": round(bandwidth, 4),
                "percent_b": round(percent_b, 4),
                "ma": round(ma, 2),
            },
        )
