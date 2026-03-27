"""Z-Score indicator — migrated from anomaly.py."""

import pandas as pd

from src.detector.base import IndicatorBase, Signal

SEVERITY_THRESHOLDS = [
    (7.0, "critical"),
    (5.0, "high"),
    (4.0, "medium"),
    (3.0, "low"),
]


def _classify_severity(z: float) -> str:
    abs_z = abs(z)
    for threshold, label in SEVERITY_THRESHOLDS:
        if abs_z >= threshold:
            return label
    return "low"


class ZScoreIndicator(IndicatorBase):
    """24h rolling z-score for price and volume."""

    MIN_CANDLES = 60  # at least 1 hour of data

    def __init__(self, weight: float = 0.30, z_threshold: float = 3.0):
        super().__init__(name="zscore", weight=weight)
        self.z_threshold = z_threshold

    def compute(self, coin_code: str, ohlcv_df: pd.DataFrame) -> Signal:
        df = self._filter_window(ohlcv_df, 1440)

        if len(df) < self.MIN_CANDLES:
            return self._not_ready(coin_code)

        current_price = df["close"].iloc[-1]
        avg_price = df["close"].mean()
        std_price = df["close"].std()

        current_volume = df["volume"].iloc[-1]
        avg_volume = df["volume"].mean()
        std_volume = df["volume"].std()

        price_z = (current_price - avg_price) / std_price if std_price > 0 else 0.0
        volume_z = (current_volume - avg_volume) / std_volume if std_volume > 0 else 0.0

        # Use the stronger signal
        max_z = price_z if abs(price_z) >= abs(volume_z) else volume_z
        is_anomaly = bool(abs(max_z) >= self.z_threshold)

        anomaly_type = "price_spike" if abs(price_z) >= abs(volume_z) else "volume_surge"

        return Signal(
            indicator_name=self.name,
            coin_code=coin_code,
            value=round(max_z, 2),
            is_anomaly=is_anomaly,
            severity=_classify_severity(max_z) if is_anomaly else "skip",
            detail={
                "price_zscore": round(price_z, 2),
                "volume_zscore": round(volume_z, 2),
                "current_price": current_price,
                "avg_price": round(avg_price, 2),
                "current_volume": current_volume,
                "avg_volume": round(avg_volume, 2),
                "anomaly_type": anomaly_type,
            },
        )
