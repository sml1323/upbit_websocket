"""RSI (Relative Strength Index) indicator."""

import pandas as pd

from src.detector.base import IndicatorBase, Signal

RSI_SEVERITY = [
    (90, 10, "critical"),
    (85, 15, "high"),
    (80, 20, "medium"),
    (75, 25, "low"),
]


class RSIIndicator(IndicatorBase):
    """RSI — overbought/oversold anomaly detection."""

    MIN_CANDLES = 60

    def __init__(self, weight: float = 0.20, window: int = 60,
                 overbought: float = 75.0, oversold: float = 25.0):
        super().__init__(name="rsi", weight=weight)
        self.window = window
        self.overbought = overbought
        self.oversold = oversold

    def compute(self, coin_code: str, ohlcv_df: pd.DataFrame) -> Signal:
        df = self._filter_window(ohlcv_df, self.window)

        if len(df) < self.MIN_CANDLES:
            return self._not_ready(coin_code)

        closes = df["close"]
        deltas = closes.diff().dropna()

        gains = deltas.where(deltas > 0, 0.0)
        losses = (-deltas).where(deltas < 0, 0.0)

        avg_gain = gains.mean()
        avg_loss = losses.mean()

        if avg_loss == 0:
            rsi = 100.0
        elif avg_gain == 0:
            rsi = 0.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        is_anomaly = bool(rsi > self.overbought or rsi < self.oversold)
        condition = "overbought" if rsi > self.overbought else "oversold" if rsi < self.oversold else "normal"

        severity = "skip"
        if is_anomaly:
            for high_th, low_th, sev in RSI_SEVERITY:
                if rsi >= high_th or rsi <= low_th:
                    severity = sev
                    break
            else:
                severity = "low"

        return Signal(
            indicator_name=self.name,
            coin_code=coin_code,
            value=round(rsi, 2),
            is_anomaly=is_anomaly,
            severity=severity,
            detail={
                "rsi_value": round(rsi, 2),
                "avg_gain": round(avg_gain, 6),
                "avg_loss": round(avg_loss, 6),
                "condition": condition,
            },
        )
