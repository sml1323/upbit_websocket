"""Legacy anomaly detection module — kept for backward compatibility.

New code should import from:
  src.detector.base      — Signal, EnsembleResult, IndicatorBase, IndicatorRegistry
  src.detector.ensemble  — EnsembleScorer, save_incident, save_snapshots
  src.detector.zscore    — ZScoreIndicator
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg2

from src.config import get_db_dsn, setup_logging

# Re-exports for backward compatibility
from src.detector.base import Signal, EnsembleResult, IndicatorBase, IndicatorRegistry  # noqa: F401
from src.detector.zscore import ZScoreIndicator  # noqa: F401
from src.detector.bollinger import BollingerBandsIndicator  # noqa: F401
from src.detector.rsi import RSIIndicator  # noqa: F401
from src.detector.vwap import VWAPIndicator  # noqa: F401

logger = setup_logging("anomaly-detector")

SEVERITY_THRESHOLDS = [
    (7.0, "critical"),
    (5.0, "high"),
    (4.0, "medium"),
    (3.0, "low"),
]

MIN_DATA_AGE_HOURS = 1  # warm-up: 최소 1시간 데이터 필요


@dataclass
class Anomaly:
    bucket: datetime
    coin_code: str
    anomaly_type: str  # 'price_spike', 'volume_surge'
    severity: str
    z_score: float
    current_value: float
    avg_value: float


def _classify_severity(z: float) -> str:
    abs_z = abs(z)
    for threshold, label in SEVERITY_THRESHOLDS:
        if abs_z >= threshold:
            return label
    return "low"


def check_warm_up(conn) -> bool:
    """데이터가 최소 MIN_DATA_AGE_HOURS 이상 쌓였는지 확인"""
    query = """
        SELECT extract(epoch FROM (now() - min(time))) / 3600
        FROM tickers
    """
    with conn.cursor() as cur:
        cur.execute(query)
        row = cur.fetchone()
        if row is None or row[0] is None:
            return False
        hours = float(row[0])
        return hours >= MIN_DATA_AGE_HOURS


def detect_anomalies(conn, z_threshold: float = 3.0) -> list[Anomaly]:
    """v_zscore 뷰에서 최근 5분간 이상 징후를 조회"""
    query = """
        SELECT
            bucket, code,
            price_zscore, volume_zscore,
            current_price, avg_price,
            current_volume, avg_volume
        FROM v_zscore
        WHERE bucket >= now() - INTERVAL '5 minutes'
          AND (ABS(price_zscore) >= %s OR ABS(volume_zscore) >= %s)
        ORDER BY bucket DESC
    """
    anomalies: list[Anomaly] = []

    with conn.cursor() as cur:
        cur.execute(query, (z_threshold, z_threshold))
        for row in cur.fetchall():
            bucket, code, pz, vz, cur_price, avg_price, cur_vol, avg_vol = row

            if abs(pz) >= z_threshold:
                anomalies.append(Anomaly(
                    bucket=bucket,
                    coin_code=code,
                    anomaly_type="price_spike",
                    severity=_classify_severity(pz),
                    z_score=round(pz, 2),
                    current_value=cur_price,
                    avg_value=avg_price,
                ))

            if abs(vz) >= z_threshold:
                anomalies.append(Anomaly(
                    bucket=bucket,
                    coin_code=code,
                    anomaly_type="volume_surge",
                    severity=_classify_severity(vz),
                    z_score=round(vz, 2),
                    current_value=cur_vol,
                    avg_value=avg_vol,
                ))

    return anomalies


def save_incident(conn, anomaly: Anomaly) -> str:
    """이상 징후를 incidents 테이블에 저장하고 incident_id 반환"""
    query = """
        INSERT INTO incidents (detected_at, coin_code, anomaly_type, severity, z_score, source)
        VALUES (%s, %s, %s, %s, %s, 'live')
        RETURNING incident_id
    """
    with conn.cursor() as cur:
        cur.execute(query, (
            anomaly.bucket, anomaly.coin_code,
            anomaly.anomaly_type, anomaly.severity, anomaly.z_score,
        ))
        incident_id = str(cur.fetchone()[0])
    conn.commit()
    logger.info(
        "Incident 저장: %s %s z=%.2f [%s]",
        anomaly.coin_code, anomaly.anomaly_type, anomaly.z_score, anomaly.severity,
    )
    return incident_id


def run_detection(z_threshold: float = 3.0) -> list[Anomaly]:
    """전체 이상 감지 파이프라인 실행"""
    conn = psycopg2.connect(get_db_dsn())
    try:
        if not check_warm_up(conn):
            logger.info("Warm-up 미완료 — 데이터 %dh 이상 필요. 스킵.", MIN_DATA_AGE_HOURS)
            return []

        anomalies = detect_anomalies(conn, z_threshold)
        if not anomalies:
            logger.debug("이상 징후 없음")
            return []

        logger.info("%d건 이상 징후 감지", len(anomalies))
        for a in anomalies:
            save_incident(conn, a)

        return anomalies
    finally:
        conn.close()
