"""React 뷰어용 /api 엔드포인트 — 노드 출력 파싱과 캔들 오버레이."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import psycopg2
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.web import _with_overlays

client = TestClient(app)

DETECTED = datetime(2026, 10, 3, 17, 34, tzinfo=timezone.utc)
REPORT = {
    "root_cause": "강세 뉴스와 대규모 매수 유입",
    "confidence": 0.9,
    "supporting_evidence": ["거래량 13.9배"],
    "alternative_hypotheses": ["고래 매집 — 근거 부족"],
    "recommended_action": "ESCALATE",
    "summary": "요약",
}


def _row(**overrides):
    row = {
        "incident_id": "57b32e03-5d20-588a-afbd-af078e072b55",
        "coin_code": "LIT",
        "severity": "critical",
        "detected_at": DETECTED,
        "source": "demo",
        "status": "analyzed",
        "ensemble_score": 1.0,
        "firing_indicators": ["zscore", "rsi"],
        "agent_report": {
            "market_analysis": json.dumps({"claim": "과열", "evidence": [], "confidence": 0.8}),
            "news_analysis": "",
            "final_report": json.dumps(REPORT, ensure_ascii=False),
        },
        "indicator_details": {
            "zscore": {"price_zscore": 3.84, "volume_zscore": -5.79},
            "rsi": {"rsi_value": 82.86, "condition": "overbought"},
            "vwap": {"deviation_pct": 0.0388},
        },
    }
    row.update(overrides)
    return row


def _mock_conn(mock_get_conn, *, fetchone=None, fetchall=None):
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall or []
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value = conn
    return cursor


class TestListIncidents:
    @patch("src.api.web._get_conn")
    def test_flattens_final_report(self, mock_get_conn):
        _mock_conn(mock_get_conn, fetchall=[_row()], fetchone={"n": 0})
        item = client.get("/api/incidents").json()["incidents"][0]
        assert item["recommended_action"] == "ESCALATE"
        assert item["confidence"] == 0.9
        assert item["root_cause"] == REPORT["root_cause"]
        assert item["has_report"] is True
        assert item["detected_at"] == DETECTED.isoformat()

    @patch("src.api.web._get_conn")
    def test_pending_and_broken_report(self, mock_get_conn):
        pending = _row(agent_report=None)
        broken = _row(agent_report={"final_report": "{not json"})
        unknown_sev = _row(severity="<script>")
        _mock_conn(mock_get_conn, fetchall=[pending, broken, unknown_sev], fetchone={"n": 0})
        items = client.get("/api/incidents").json()["incidents"]
        assert [i["has_report"] for i in items[:2]] == [False, False]
        assert items[0]["recommended_action"] is None
        assert items[2]["severity"] == "low"


    @patch("src.api.web._get_conn")
    def test_hides_skipped_unless_asked(self, mock_get_conn):
        cursor = _mock_conn(mock_get_conn, fetchone={"n": 73})
        data = client.get("/api/incidents").json()
        assert data["skipped_count"] == 73
        assert "'skipped'" in cursor.execute.call_args_list[0].args[0]
        client.get("/api/incidents?include_skipped=true")
        assert "skipped" not in cursor.execute.call_args_list[2].args[0]


class TestGetIncident:
    @patch("src.api.web._get_conn")
    def test_parses_nodes_and_indicators(self, mock_get_conn):
        _mock_conn(mock_get_conn, fetchone=_row())
        data = client.get("/api/incidents/57b32e03-5d20-588a-afbd-af078e072b55").json()
        assert data["report"]["summary"] == "요약"
        assert data["market"]["claim"] == "과열"
        assert data["news"] is None
        assert "news_articles" not in data  # 에이전트가 저장하지 않는 값은 내려주지 않는다
        by_name = {i["name"]: i for i in data["indicators"]}
        # zscore 는 가격·거래량 중 절댓값이 큰 쪽
        assert by_name["zscore"]["value"] == -5.79
        assert by_name["rsi"] == {
            "name": "rsi", "value": 82.86, "firing": True,
            "detail": {"rsi_value": 82.86, "condition": "overbought"},
        }
        assert by_name["vwap"]["firing"] is False

    @patch("src.api.web._get_conn")
    def test_not_found(self, mock_get_conn):
        _mock_conn(mock_get_conn, fetchone=None)
        assert client.get("/api/incidents/57b32e03-5d20-588a-afbd-af078e072b55").status_code == 404

    @patch("src.api.web._get_conn")
    def test_invalid_uuid_is_404(self, mock_get_conn):
        cursor = _mock_conn(mock_get_conn)
        cursor.execute.side_effect = psycopg2.errors.InvalidTextRepresentation("bad uuid")
        assert client.get("/api/incidents/not-a-uuid").status_code == 404


class TestCandles:
    @patch("src.api.web._get_conn")
    def test_queries_window_around_detection(self, mock_get_conn):
        bucket = DETECTED - timedelta(minutes=1)
        cursor = _mock_conn(mock_get_conn, fetchone=_row(), fetchall=[{
            "bucket": bucket, "open": 1, "high": 3, "low": 1, "close": 2,
            "volume": 10, "trade_count": 4,
        }])
        data = client.get("/api/incidents/x/candles?before=60&after=15").json()
        sql, params = cursor.execute.call_args[0]
        assert "agg_1min" in sql
        assert params == ("LIT", DETECTED - timedelta(minutes=60), DETECTED + timedelta(minutes=15))
        assert data["candles"][0]["t"] == bucket.isoformat()
        assert data["candles"][0]["vwap"] == 2.0

    def test_window_limits(self):
        assert client.get("/api/incidents/x/candles?before=5000").status_code == 422


def test_overlays_vwap_and_bollinger():
    candles = [
        {"high": c, "low": c, "close": c, "volume": 1.0 if c < 30 else 3.0}
        for c in [10.0] * 19 + [30.0]
    ]
    out = _with_overlays(candles)
    assert out[18]["bb_mid"] is None  # 20봉이 차기 전엔 밴드 없음
    assert out[19]["bb_mid"] == 11.0
    assert out[19]["close"] > out[19]["bb_upper"] > out[19]["bb_mid"]  # 급등봉은 상단 밖
    # 누적 VWAP = (19×10×1 + 30×3) / (19 + 3)
    assert abs(out[19]["vwap"] - (190 + 90) / 22) < 1e-9
