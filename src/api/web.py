"""React 리포트 뷰어(frontend/)가 쓰는 JSON API.

기존 /incidents 는 DB 행을 그대로 돌려준다(agent_report 안의 노드 출력이 JSON 문자열).
여기서는 화면이 바로 쓸 수 있게 노드 출력을 파싱해 평평한 모양으로 내려준다.
"""

import json
import math
from datetime import timedelta

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Query

from src.config import get_db_dsn

router = APIRouter(prefix="/api", tags=["viewer"])

ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}
BOLLINGER_WINDOW = 20


def _get_conn():
    return psycopg2.connect(get_db_dsn(), cursor_factory=RealDictCursor)


def _parse(raw):
    """노드 출력은 JSON 문자열로 저장된다. 이미 dict 면 그대로, 깨졌으면 None."""
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _num(value):
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def _report_parts(row: dict) -> tuple[dict | None, dict | None, dict | None]:
    agent_report = row.get("agent_report") or {}
    if not isinstance(agent_report, dict):
        return None, None, None
    return (
        _parse(agent_report.get("market_analysis")),
        _parse(agent_report.get("news_analysis")),
        _parse(agent_report.get("final_report")),
    )


def _summary(row: dict) -> dict:
    _, _, report = _report_parts(row)
    severity = str(row.get("severity") or "low").lower()
    return {
        "incident_id": str(row["incident_id"]),
        "coin_code": row["coin_code"],
        "severity": severity if severity in ALLOWED_SEVERITIES else "low",
        "detected_at": row["detected_at"].isoformat(),
        "source": row.get("source"),
        "status": row.get("status"),
        "ensemble_score": _num(row.get("ensemble_score")),
        "firing_indicators": list(row.get("firing_indicators") or []),
        "confidence": _num(report.get("confidence")) if report else None,
        "recommended_action": report.get("recommended_action") if report else None,
        "root_cause": report.get("root_cause") if report else None,
        "has_report": report is not None,
    }


# 지표별 대표값 — detector 가 남기는 detail 키 중 화면에 보여줄 하나
_INDICATOR_VALUE_KEY = {
    "bollinger_bands": "percent_b",
    "rsi": "rsi_value",
    "vwap": "deviation_pct",
}


def _indicators(row: dict) -> list[dict]:
    details = row.get("indicator_details") or {}
    if not isinstance(details, dict):
        return []
    firing = set(row.get("firing_indicators") or [])
    out = []
    for name, detail in details.items():
        detail = detail if isinstance(detail, dict) else {}
        if name == "zscore":
            # 가격·거래량 중 더 크게 벗어난 쪽이 발화 이유다
            zs = [z for z in (_num(detail.get("price_zscore")), _num(detail.get("volume_zscore"))) if z is not None]
            value = max(zs, key=abs) if zs else None
        else:
            key = _INDICATOR_VALUE_KEY.get(name)
            value = _num(detail.get(key)) if key else None
        out.append({
            "name": name,
            "value": value,
            "firing": name in firing,
            "detail": {k: v for k, v in detail.items() if isinstance(v, (int, float, str))},
        })
    return out


@router.get("/incidents")
def list_incidents(
    limit: int = Query(50, ge=1, le=200),
    include_skipped: bool = Query(False, description="사이클 분석 상한에 밀려 감지만 저장된 건 포함"),
):
    where = "" if include_skipped else "WHERE status IS DISTINCT FROM 'skipped'"
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT incident_id, coin_code, severity, detected_at, source, status,
                           ensemble_score, firing_indicators, agent_report
                    FROM incidents {where} ORDER BY detected_at DESC LIMIT %s""",
                (limit,),
            )
            rows = cur.fetchall()
            cur.execute("SELECT count(*) AS n FROM incidents WHERE status = 'skipped'")
            skipped = cur.fetchone()["n"]
    finally:
        conn.close()
    return {"incidents": [_summary(r) for r in rows], "skipped_count": skipped}


def _fetch_incident(cur, incident_id: str) -> dict:
    try:
        cur.execute("SELECT * FROM incidents WHERE incident_id = %s::uuid", (incident_id,))
    except psycopg2.errors.InvalidTextRepresentation:
        raise HTTPException(status_code=404, detail="Incident not found")
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")
    return row


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            row = _fetch_incident(cur, incident_id)
    finally:
        conn.close()
    market, news, report = _report_parts(row)
    return {
        **_summary(row),
        "indicators": _indicators(row),
        "market": market,
        "news": news,
        "report": report,
    }


def _with_overlays(candles: list[dict]) -> list[dict]:
    """창 전체 누적 VWAP 과 20봉 볼린저 밴드(±2σ)를 붙인다."""
    cum_pv = cum_v = 0.0
    closes: list[float] = []
    for c in candles:
        typical = (c["high"] + c["low"] + c["close"]) / 3
        cum_pv += typical * c["volume"]
        cum_v += c["volume"]
        c["vwap"] = cum_pv / cum_v if cum_v > 0 else None

        closes.append(c["close"])
        window = closes[-BOLLINGER_WINDOW:]
        if len(window) == BOLLINGER_WINDOW:
            mid = sum(window) / BOLLINGER_WINDOW
            sd = math.sqrt(sum((x - mid) ** 2 for x in window) / BOLLINGER_WINDOW)
            c["bb_mid"], c["bb_upper"], c["bb_lower"] = mid, mid + 2 * sd, mid - 2 * sd
        else:
            c["bb_mid"] = c["bb_upper"] = c["bb_lower"] = None
    return candles


@router.get("/incidents/{incident_id}/candles")
def get_candles(
    incident_id: str,
    before: int = Query(90, ge=10, le=720, description="감지 시점 이전 분"),
    after: int = Query(30, ge=0, le=240, description="감지 시점 이후 분"),
):
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            row = _fetch_incident(cur, incident_id)
            detected_at = row["detected_at"]
            cur.execute(
                """SELECT bucket, open, high, low, close, volume, trade_count
                   FROM agg_1min
                   WHERE code = %s AND bucket BETWEEN %s AND %s
                   ORDER BY bucket""",
                (row["coin_code"], detected_at - timedelta(minutes=before),
                 detected_at + timedelta(minutes=after)),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    candles = [
        {
            "t": r["bucket"].isoformat(),
            "open": float(r["open"]), "high": float(r["high"]),
            "low": float(r["low"]), "close": float(r["close"]),
            "volume": float(r["volume"]), "trades": int(r["trade_count"] or 0),
        }
        for r in rows
    ]
    return {"detected_at": detected_at.isoformat(), "candles": _with_overlays(candles)}
