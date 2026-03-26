import json
from datetime import datetime, timezone
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.config import get_db_dsn, setup_logging
from src.detector.anomaly import Anomaly, detect_anomalies, save_incident
from src.agent.graph import analyze_anomaly

logger = setup_logging("api")

app = FastAPI(
    title="Market Incident Copilot",
    description="Upbit 시세 이상 감지 + AI Agent 분석 API",
    version="0.1.0",
)


def _get_conn():
    return psycopg2.connect(get_db_dsn(), cursor_factory=RealDictCursor)


# ── GET /incidents ──────────────────────────────────────────
@app.get("/incidents")
def list_incidents(limit: int = 20, source: str | None = None):
    """최근 incident 목록 조회"""
    query = "SELECT * FROM incidents"
    params: list = []

    if source:
        query += " WHERE source = %s"
        params.append(source)

    query += " ORDER BY detected_at DESC LIMIT %s"
    params.append(limit)

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return {"count": len(rows), "incidents": rows}
    finally:
        conn.close()


# ── GET /incidents/{id} ────────────────────────────────────
@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    """Incident 상세 조회"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM incidents WHERE incident_id = %s::uuid",
                (incident_id,),
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Incident not found")
        return row
    finally:
        conn.close()


# ── POST /replay ───────────────────────────────────────────
class ReplayRequest(BaseModel):
    coin_code: str
    replay_at: datetime
    z_threshold: float = 3.0


@app.post("/replay")
def replay_incident(req: ReplayRequest):
    """과거 시점을 기준으로 이상 감지를 재실행합니다.

    해당 시점까지의 데이터만으로 Agent를 실행하고,
    source='replay' 플래그가 붙은 incident를 생성합니다.
    """
    query = """
        WITH stats AS (
            SELECT
                bucket, code, close, volume,
                AVG(close) OVER w    AS avg_price,
                STDDEV(close) OVER w AS stddev_price,
                AVG(volume) OVER w   AS avg_volume,
                STDDEV(volume) OVER w AS stddev_volume,
                SUM(trade_count) OVER w AS total_trades_24h
            FROM agg_1min
            WHERE code = %s AND bucket <= %s
            WINDOW w AS (
                PARTITION BY code ORDER BY bucket
                ROWS BETWEEN 1439 PRECEDING AND CURRENT ROW
            )
        )
        SELECT
            bucket, code, close, volume,
            avg_price, stddev_price, avg_volume, stddev_volume,
            CASE WHEN stddev_price > 0 THEN (close - avg_price) / stddev_price ELSE 0 END AS price_zscore,
            CASE WHEN stddev_volume > 0 THEN (volume - avg_volume) / stddev_volume ELSE 0 END AS volume_zscore
        FROM stats
        WHERE total_trades_24h >= 100
        ORDER BY bucket DESC
        LIMIT 1
    """
    conn = psycopg2.connect(get_db_dsn())
    try:
        with conn.cursor() as cur:
            cur.execute(query, (req.coin_code, req.replay_at))
            row = cur.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"{req.coin_code}: {req.replay_at} 시점 데이터 없음",
            )

        bucket, code, close, volume, avg_p, std_p, avg_v, std_v, pz, vz = row
        anomalies = []

        if abs(pz) >= req.z_threshold:
            anomalies.append(("price_spike", pz, close, avg_p))
        if abs(vz) >= req.z_threshold:
            anomalies.append(("volume_surge", vz, volume, avg_v))

        if not anomalies:
            return {
                "message": f"{code}@{bucket}: 이상 징후 없음 (z-threshold={req.z_threshold})",
                "price_zscore": round(pz, 2),
                "volume_zscore": round(vz, 2),
            }

        results = []
        for atype, z, cur_val, avg_val in anomalies:
            from src.detector.anomaly import _classify_severity
            severity = _classify_severity(z)

            # replay incident 저장
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO incidents
                       (detected_at, coin_code, anomaly_type, severity, z_score, source)
                       VALUES (%s, %s, %s, %s, %s, 'replay')
                       RETURNING incident_id""",
                    (bucket, code, atype, severity, round(z, 2)),
                )
                incident_id = str(cur.fetchone()[0])
            conn.commit()

            # Agent 분석
            anomaly = Anomaly(
                bucket=bucket, coin_code=code, anomaly_type=atype,
                severity=severity, z_score=round(z, 2),
                current_value=cur_val, avg_value=avg_val,
            )
            analyze_anomaly(anomaly, incident_id)

            results.append({
                "incident_id": incident_id,
                "anomaly_type": atype,
                "severity": severity,
                "z_score": round(z, 2),
            })

        return {"replay_at": str(req.replay_at), "coin_code": code, "incidents": results}

    finally:
        conn.close()
