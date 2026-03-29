"""Ensemble scorer — combines multiple indicators with weighted voting."""

import json

import pandas as pd
import psycopg2

from src.detector.base import (
    EnsembleResult,
    IndicatorRegistry,
    Signal,
)
from src.config import setup_logging

logger = setup_logging("ensemble-scorer")

SEVERITY_BY_FIRING_COUNT = {
    1: "low",
    2: "medium",
    3: "high",
}


def _compute_severity(firing_count: int) -> str:
    if firing_count >= 4:
        return "critical"
    return SEVERITY_BY_FIRING_COUNT.get(firing_count, "low")


def fetch_ohlcv_batch(
    conn, coin_codes: list[str], window_minutes: int = 1440
) -> pd.DataFrame:
    """Fetch OHLCV data for multiple coins in a single query."""
    if not coin_codes:
        return pd.DataFrame(columns=["bucket", "code", "open", "high", "low", "close", "volume", "trade_count"])

    query = """
        SELECT bucket, code, open, high, low, close, volume, trade_count
        FROM agg_1min
        WHERE code = ANY(%s)
          AND bucket >= now() - make_interval(mins := %s)
        ORDER BY code, bucket
    """
    with conn.cursor() as cur:
        cur.execute(query, (coin_codes, window_minutes))
        rows = cur.fetchall()

    columns = ["bucket", "code", "open", "high", "low", "close", "volume", "trade_count"]
    return pd.DataFrame(rows, columns=columns)


def prefilter_coins(conn, z_threshold: float = 2.0) -> list[str]:
    """Pre-filter coins using existing v_zscore view."""
    query = """
        SELECT DISTINCT code
        FROM v_zscore
        WHERE bucket >= now() - INTERVAL '5 minutes'
          AND (ABS(price_zscore) >= %s OR ABS(volume_zscore) >= %s)
    """
    with conn.cursor() as cur:
        cur.execute(query, (z_threshold, z_threshold))
        return [row[0] for row in cur.fetchall()]


class EnsembleScorer:
    """Weighted ensemble of registered indicators."""

    def __init__(self, registry: IndicatorRegistry):
        self.registry = registry

    def score(self, coin_code: str, ohlcv_df: pd.DataFrame) -> EnsembleResult:
        """Score a single coin against all registered indicators."""
        coin_df = ohlcv_df[ohlcv_df["code"] == coin_code] if "code" in ohlcv_df.columns else ohlcv_df

        pairs: list[tuple] = []
        for ind in self.registry.get_all():
            try:
                signal = ind.compute(coin_code, coin_df)
            except Exception as e:
                logger.warning("Indicator %s failed for %s: %s", ind.name, coin_code, e)
                signal = Signal(
                    indicator_name=ind.name,
                    coin_code=coin_code,
                    value=0.0,
                    is_anomaly=False,
                    severity="skip",
                    detail={"error": str(e)},
                    ready=False,
                )
            pairs.append((ind, signal))

        active = [(ind, sig) for ind, sig in pairs if sig.ready]
        active_weight_sum = sum(ind.weight for ind, _ in active)

        if active_weight_sum == 0:
            return EnsembleResult(
                coin_code=coin_code,
                is_anomaly=False,
                ensemble_score=0.0,
                firing_count=0,
                signals=[sig for _, sig in pairs],
                severity="skip",
                active_indicator_count=0,
            )

        weighted_sum = sum(
            ind.weight * (1.0 if sig.is_anomaly else 0.0)
            for ind, sig in active
        ) / active_weight_sum

        firing_count = sum(1 for _, sig in active if sig.is_anomaly)
        is_anomaly = weighted_sum >= 0.5

        return EnsembleResult(
            coin_code=coin_code,
            is_anomaly=is_anomaly,
            ensemble_score=round(weighted_sum, 4),
            firing_count=firing_count,
            signals=[sig for _, sig in pairs],
            severity=_compute_severity(firing_count) if is_anomaly else "skip",
            active_indicator_count=len(active),
        )

    def score_batch(self, coin_codes: list[str], conn) -> list[EnsembleResult]:
        """Score multiple coins with a single DB fetch."""
        ohlcv_all = fetch_ohlcv_batch(conn, coin_codes, window_minutes=1440)
        return [self.score(code, ohlcv_all) for code in coin_codes]


def _to_native(val):
    """Convert numpy types to Python native for psycopg2."""
    if val is None:
        return None
    if hasattr(val, 'item'):
        return val.item()
    return val


def _clean_detail(detail: dict) -> dict:
    """Convert all numpy values in a detail dict to native Python types."""
    return {k: _to_native(v) for k, v in detail.items()}


def save_incident(conn, result: EnsembleResult) -> str:
    """Save an ensemble anomaly to the incidents table."""
    firing_names = [s.indicator_name for s in result.signals if s.is_anomaly]
    details = {s.indicator_name: _clean_detail(s.detail) for s in result.signals if s.ready}
    z_score_val = None
    for s in result.signals:
        if s.indicator_name == "zscore" and s.ready:
            z_score_val = _to_native(s.value)
            break

    query = """
        INSERT INTO incidents
            (coin_code, anomaly_type, severity, z_score, source,
             ensemble_score, firing_indicators, indicator_details)
        VALUES (%s, %s, %s, %s, 'live', %s, %s, %s)
        RETURNING incident_id
    """
    anomaly_type = "ensemble"
    if result.firing_count == 1 and firing_names:
        anomaly_type = firing_names[0]

    with conn.cursor() as cur:
        cur.execute(query, (
            result.coin_code,
            anomaly_type,
            result.severity,
            z_score_val,
            _to_native(result.ensemble_score),
            firing_names,
            json.dumps(details, default=str),
        ))
        incident_id = str(cur.fetchone()[0])
    conn.commit()

    logger.info(
        "Incident saved: %s score=%.2f firing=%s [%s]",
        result.coin_code, result.ensemble_score,
        firing_names, result.severity,
    )
    return incident_id


def save_snapshots(conn, results: list[EnsembleResult]) -> None:
    """Save indicator values to indicator_snapshots for Grafana."""
    rows = []
    for result in results:
        for signal in result.signals:
            if not signal.ready:
                continue
            # Convert numpy types to Python native for psycopg2
            value = float(signal.value) if signal.value is not None else None
            is_anom = bool(signal.is_anomaly)
            detail = {k: float(v) if hasattr(v, 'item') else v
                      for k, v in signal.detail.items()}
            rows.append((
                signal.coin_code,
                signal.indicator_name,
                value,
                is_anom,
                json.dumps(detail),
            ))

    if not rows:
        return

    query = """
        INSERT INTO indicator_snapshots (time, coin_code, indicator, value, is_anomaly, detail)
        VALUES (now(), %s, %s, %s, %s, %s)
    """
    with conn.cursor() as cur:
        cur.executemany(query, rows)
    conn.commit()
    logger.debug("Saved %d indicator snapshots", len(rows))
