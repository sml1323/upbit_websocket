from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import json

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestListIncidents:
    @patch("src.api.main._get_conn")
    def test_list_incidents(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "incident_id": "abc-123",
                "detected_at": datetime.now(timezone.utc),
                "coin_code": "BTC",
                "anomaly_type": "price_spike",
                "severity": "high",
                "z_score": 5.5,
                "source": "live",
                "status": "open",
            }
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.get("/incidents")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["incidents"][0]["coin_code"] == "BTC"

    @patch("src.api.main._get_conn")
    def test_list_incidents_empty(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.get("/incidents")
        assert response.status_code == 200
        assert response.json()["count"] == 0

    @patch("src.api.main._get_conn")
    def test_list_incidents_with_source_filter(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.get("/incidents?source=replay")
        assert response.status_code == 200
        # source 파라미터가 쿼리에 반영되었는지 확인
        call_args = mock_cursor.execute.call_args
        assert "source" in call_args[0][0].lower() or "replay" in str(call_args[0][1])


class TestGetIncident:
    @patch("src.api.main._get_conn")
    def test_get_incident_found(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "incident_id": "abc-123",
            "coin_code": "ETH",
            "severity": "medium",
        }
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.get("/incidents/abc-123")
        assert response.status_code == 200
        assert response.json()["coin_code"] == "ETH"

    @patch("src.api.main._get_conn")
    def test_get_incident_not_found(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.get("/incidents/nonexistent")
        assert response.status_code == 404


class TestReportHtmlSecurity:
    @patch("src.api.main._get_conn")
    def test_report_detail_escapes_agent_report_content(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "incident_id": "abc-123",
            "detected_at": datetime.now(timezone.utc),
            "coin_code": "BTC<script>alert(1)</script>",
            "severity": "high",
            "ensemble_score": 0.85,
            "confidence_score": 0.8,
            "firing_indicators": ["zscore"],
            "indicator_details": {
                "zscore": {"price_zscore": "<b>5.2</b>"},
            },
            "agent_report": {
                "market_analysis": json.dumps({
                    "claim": "<script>alert(1)</script>",
                    "evidence": ["<img src=x onerror=alert(1)>"],
                    "confidence": 0.85,
                    "missing_data": [],
                }),
                "news_analysis": json.dumps({
                    "headlines": ["<iframe src=evil></iframe>"],
                    "sentiment": "NEUTRAL",
                    "relevance_score": 0.0,
                    "source_quality": "unknown",
                }),
                "final_report": json.dumps({
                    "summary": "<script>alert(2)</script>",
                    "root_cause": "test",
                    "confidence": 0.8,
                    "supporting_evidence": [],
                    "alternative_hypotheses": [],
                    "recommended_action": "MONITOR",
                }),
            },
        }
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.get("/reports/abc-123")

        assert response.status_code == 200
        assert "<script>alert(1)</script>" not in response.text
        assert "<script>alert(2)</script>" not in response.text
        assert "<img src=x onerror=alert(1)>" not in response.text
        assert "<iframe src=evil></iframe>" not in response.text
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text
        assert "&lt;img src=x onerror=alert(1)&gt;" in response.text

    @patch("src.api.main._get_conn")
    def test_report_list_escapes_row_content_and_rejects_bad_severity(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "incident_id": "abc-123",
                "detected_at": datetime.now(timezone.utc),
                "coin_code": "<img src=x onerror=alert(1)>",
                "severity": 'high" onclick="alert(1)',
                "ensemble_score": 0.85,
                "confidence_score": 0.8,
                "firing_indicators": ["<script>alert(3)</script>"],
                "has_report": True,
            }
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.get("/reports")

        assert response.status_code == 200
        assert "<img src=x onerror=alert(1)>" not in response.text
        assert "<script>alert(3)</script>" not in response.text
        assert 'onclick="alert(1)' not in response.text
        assert "badge-low" in response.text
        assert "&lt;img src=x onerror=alert(1)&gt;" in response.text
        assert "&lt;script&gt;alert(3)&lt;/script&gt;" in response.text
