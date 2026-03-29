import json
from datetime import datetime, timezone
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.config import get_db_dsn, setup_logging
from src.detector.anomaly import Anomaly, detect_anomalies, save_incident
from src.agent.graph import analyze_anomaly

logger = setup_logging("api")

app = FastAPI(
    title="Market Incident Copilot",
    description="Upbit 시세 이상 감지 + AI Agent 분석 API",
    version="0.2.0",
)


def _get_conn():
    return psycopg2.connect(get_db_dsn(), cursor_factory=RealDictCursor)


# ── HTML Report Viewer ────────────────────────────────────

REPORT_LIST_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Market Incident Copilot</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0d1117; color: #c9d1d9; }
  .container { max-width: 900px; margin: 0 auto; padding: 24px; }
  h1 { font-size: 24px; margin-bottom: 8px; color: #f0f6fc; }
  .subtitle { color: #8b949e; margin-bottom: 24px; font-size: 14px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
          padding: 16px; margin-bottom: 12px; cursor: pointer;
          transition: border-color 0.2s; }
  .card:hover { border-color: #58a6ff; }
  .card-header { display: flex; justify-content: space-between; align-items: center; }
  .coin { font-size: 18px; font-weight: 700; color: #f0f6fc; }
  .badge { padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
  .badge-low { background: #238636; color: #fff; }
  .badge-medium { background: #d29922; color: #000; }
  .badge-high { background: #da3633; color: #fff; }
  .badge-critical { background: #f85149; color: #fff; animation: pulse 1.5s infinite; }
  @keyframes pulse { 50% { opacity: 0.7; } }
  .meta { color: #8b949e; font-size: 13px; margin-top: 8px; }
  .meta span { margin-right: 16px; }
  .indicators { margin-top: 8px; }
  .indicator-tag { display: inline-block; padding: 2px 6px; margin-right: 4px;
                   background: #1f2937; border-radius: 4px; font-size: 12px; color: #79c0ff; }
  .no-data { text-align: center; color: #8b949e; padding: 60px; }
  a { color: inherit; text-decoration: none; }
</style>
</head>
<body>
<div class="container">
  <h1>Market Incident Copilot</h1>
  <p class="subtitle">Multi-Agent AI 분석 리포트</p>
  {cards}
</div>
</body>
</html>"""

REPORT_DETAIL_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{coin} Incident Report</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0d1117; color: #c9d1d9; }
  .container { max-width: 900px; margin: 0 auto; padding: 24px; }
  .back { color: #58a6ff; text-decoration: none; font-size: 14px; }
  .back:hover { text-decoration: underline; }
  .header { margin: 16px 0 24px; }
  .header h1 { font-size: 28px; color: #f0f6fc; }
  .header .meta { color: #8b949e; font-size: 14px; margin-top: 4px; }
  .badge { padding: 3px 10px; border-radius: 12px; font-size: 13px; font-weight: 600; }
  .badge-low { background: #238636; color: #fff; }
  .badge-medium { background: #d29922; color: #000; }
  .badge-high { background: #da3633; color: #fff; }
  .badge-critical { background: #f85149; color: #fff; }
  .score-bar { display: flex; gap: 24px; margin: 16px 0; }
  .score-item { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                padding: 12px 20px; text-align: center; flex: 1; }
  .score-value { font-size: 28px; font-weight: 700; color: #f0f6fc; }
  .score-label { font-size: 12px; color: #8b949e; margin-top: 4px; }
  .section { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
             margin-bottom: 16px; overflow: hidden; }
  .section-header { padding: 12px 16px; border-bottom: 1px solid #30363d;
                    display: flex; align-items: center; gap: 8px; }
  .section-icon { font-size: 18px; }
  .section-title { font-size: 15px; font-weight: 600; color: #f0f6fc; }
  .section-agent { font-size: 11px; color: #8b949e; background: #1f2937;
                   padding: 2px 6px; border-radius: 4px; margin-left: auto; }
  .section-body { padding: 16px; line-height: 1.7; font-size: 14px;
                  white-space: pre-wrap; }
  .indicator-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                    gap: 12px; padding: 16px; }
  .indicator-card { background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
                    padding: 12px; }
  .indicator-name { font-size: 12px; color: #8b949e; text-transform: uppercase; }
  .indicator-value { font-size: 20px; font-weight: 700; color: #f0f6fc; margin-top: 4px; }
  .indicator-status { font-size: 12px; margin-top: 4px; }
  .status-anomaly { color: #f85149; }
  .status-normal { color: #3fb950; }
  .no-report { color: #8b949e; padding: 40px; text-align: center; }
</style>
</head>
<body>
<div class="container">
  <a href="/reports" class="back">&larr; 목록으로</a>

  <div class="header">
    <h1>{coin} <span class="badge badge-{severity}">{severity_upper}</span></h1>
    <div class="meta">{detected_at} &middot; ID: {incident_id}</div>
  </div>

  <div class="score-bar">
    <div class="score-item">
      <div class="score-value">{ensemble_score}</div>
      <div class="score-label">Ensemble Score</div>
    </div>
    <div class="score-item">
      <div class="score-value">{confidence}</div>
      <div class="score-label">AI Confidence</div>
    </div>
    <div class="score-item">
      <div class="score-value">{firing_count}</div>
      <div class="score-label">Firing Indicators</div>
    </div>
  </div>

  {indicators_section}
  {market_section}
  {news_section}
  {report_section}
</div>
</body>
</html>"""


def _severity_badge(sev):
    return f'<span class="badge badge-{sev}">{sev.upper()}</span>'


def _build_indicator_section(details):
    if not details:
        return ""
    cards = ""
    for name, detail in details.items():
        if isinstance(detail, dict):
            value = detail.get("rsi_value") or detail.get("percent_b") or detail.get("deviation_pct") or detail.get("price_zscore") or ""
            if isinstance(value, (int, float)):
                value = f"{value:.2f}"
        else:
            value = str(detail)
        cards += f"""<div class="indicator-card">
  <div class="indicator-name">{name}</div>
  <div class="indicator-value">{value}</div>
</div>"""
    return f"""<div class="section">
  <div class="section-header">
    <span class="section-icon">📊</span>
    <span class="section-title">앙상블 지표 상세</span>
    <span class="section-agent">EnsembleScorer</span>
  </div>
  <div class="indicator-grid">{cards}</div>
</div>"""


def _build_agent_section(icon, title, agent_name, content):
    if not content:
        return ""
    return f"""<div class="section">
  <div class="section-header">
    <span class="section-icon">{icon}</span>
    <span class="section-title">{title}</span>
    <span class="section-agent">{agent_name}</span>
  </div>
  <div class="section-body">{content}</div>
</div>"""


@app.get("/reports", response_class=HTMLResponse)
def report_list(limit: int = 30):
    """HTML 리포트 목록"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT incident_id, coin_code, severity, ensemble_score,
                       firing_indicators, confidence_score, detected_at,
                       agent_report IS NOT NULL AS has_report
                FROM incidents
                ORDER BY detected_at DESC LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return REPORT_LIST_HTML.replace("{cards}", '<div class="no-data">아직 인시던트가 없습니다.</div>')

    cards = ""
    for r in rows:
        sev = r["severity"] or "low"
        firing = r.get("firing_indicators") or []
        score = r.get("ensemble_score")
        score_str = f"{score:.2f}" if score is not None else "-"
        confidence = r.get("confidence_score")
        conf_str = f"{confidence:.1f}" if confidence is not None else "-"
        has_report = r.get("has_report", False)
        report_icon = "📝" if has_report else "⏳"

        indicator_tags = "".join(f'<span class="indicator-tag">{f}</span>' for f in firing)

        cards += f"""<a href="/reports/{r['incident_id']}">
<div class="card">
  <div class="card-header">
    <span class="coin">{report_icon} {r['coin_code']}</span>
    <span class="badge badge-{sev}">{sev.upper()}</span>
  </div>
  <div class="meta">
    <span>Score: {score_str}</span>
    <span>Confidence: {conf_str}</span>
    <span>{r['detected_at']}</span>
  </div>
  <div class="indicators">{indicator_tags}</div>
</div></a>"""

    return REPORT_LIST_HTML.replace("{cards}", cards)


@app.get("/reports/{incident_id}", response_class=HTMLResponse)
def report_detail(incident_id: str):
    """HTML 리포트 상세"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM incidents WHERE incident_id = %s::uuid", (incident_id,))
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")

    sev = row.get("severity") or "low"
    score = row.get("ensemble_score")
    confidence = row.get("confidence_score")
    firing = row.get("firing_indicators") or []
    agent_report = row.get("agent_report") or {}
    indicator_details = row.get("indicator_details") or {}

    # agent_report 구조: {market_analysis, news_analysis, final_report, indicator_details}
    # 이전 형식: {text: "..."} 호환
    if "market_analysis" in agent_report:
        market = agent_report.get("market_analysis", "")
        news = agent_report.get("news_analysis", "")
        report = agent_report.get("final_report", "")
        if not indicator_details and "indicator_details" in agent_report:
            indicator_details = agent_report["indicator_details"]
    elif "text" in agent_report:
        market = ""
        news = ""
        report = agent_report["text"]
    else:
        market = ""
        news = ""
        report = ""

    indicators_section = _build_indicator_section(
        indicator_details if isinstance(indicator_details, dict) else {}
    )
    market_section = _build_agent_section("📈", "시장 분석", "Market Agent", market)
    news_section = _build_agent_section("📰", "뉴스 분석", "News Agent", news)
    report_section = _build_agent_section("📋", "최종 리포트", "Report Agent", report)

    if not market and not news and not report:
        report_section = '<div class="no-report">Agent 분석이 아직 완료되지 않았습니다.</div>'

    html = (REPORT_DETAIL_HTML
        .replace("{coin}", row["coin_code"])
        .replace("{severity}", sev)
        .replace("{severity_upper}", sev.upper())
        .replace("{detected_at}", str(row["detected_at"]))
        .replace("{incident_id}", incident_id)
        .replace("{ensemble_score}", f"{score:.2f}" if score is not None else "-")
        .replace("{confidence}", f"{confidence:.1f}" if confidence is not None else "-")
        .replace("{firing_count}", str(len(firing)))
        .replace("{indicators_section}", indicators_section)
        .replace("{market_section}", market_section)
        .replace("{news_section}", news_section)
        .replace("{report_section}", report_section)
    )
    return html


# ── JSON API (기존 유지) ──────────────────────────────────

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
    """과거 시점을 기준으로 이상 감지를 재실행합니다."""
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
