from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from src.agent.tools.query_market import query_market_window
from src.agent.tools.search_news import (
    _search_cryptopanic,
    _search_serpapi,
    search_news,
)
from src.agent.tools.write_report import write_incident_report


class TestQueryMarketWindow:
    @patch("src.agent.tools.query_market.psycopg2.connect")
    def test_returns_summary(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        now = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            (now, 50500000, 50800000, 50100000, 50600000, 1.5, 30),
            (now, 50000000, 50200000, 49800000, 50100000, 1.2, 25),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        result = query_market_window.invoke({"coin_code": "BTC", "minutes": 60})
        assert "BTC" in result
        assert "변동률" in result

    @patch("src.agent.tools.query_market.psycopg2.connect")
    def test_no_data(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        result = query_market_window.invoke({"coin_code": "XYZ", "minutes": 60})
        assert "데이터 없음" in result


class TestSearchNews:
    @patch("src.agent.tools.search_news.requests.get")
    @patch("src.agent.tools.search_news.CRYPTOPANIC_API_KEY", "test-key")
    def test_cryptopanic_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {"title": "BTC surges", "url": "http://example.com", "source": {"title": "CoinDesk"}},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = _search_cryptopanic("BTC")
        assert len(result) == 1
        assert result[0]["title"] == "BTC surges"

    @patch("src.agent.tools.search_news.CRYPTOPANIC_API_KEY", "")
    def test_cryptopanic_no_key(self):
        result = _search_cryptopanic("BTC")
        assert result is None

    @patch("src.agent.tools.search_news._search_cryptopanic", return_value=None)
    @patch("src.agent.tools.search_news._search_serpapi", return_value=None)
    def test_search_news_no_results(self, mock_serp, mock_crypto):
        result = search_news.invoke({"coin_code": "UNKNOWN"})
        assert "찾을 수 없습니다" in result

    @patch("src.agent.tools.search_news._search_cryptopanic")
    def test_search_news_with_results(self, mock_crypto):
        mock_crypto.return_value = [
            {"title": "ETH update", "url": "http://ex.com", "source": "CoinTelegraph"},
        ]
        result = search_news.invoke({"coin_code": "ETH"})
        assert "ETH" in result
        assert "1건" in result


class TestWriteReport:
    @patch("src.agent.tools.write_report.psycopg2.connect")
    def test_successful_write(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("abc-123",)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        result = write_incident_report.invoke({
            "incident_id": "abc-123",
            "report_text": "BTC 급등 분석",
            "confidence_score": 0.85,
            "news_context": "뉴스 내용",
        })
        assert "저장 완료" in result
        mock_conn.commit.assert_called_once()

    @patch("src.agent.tools.write_report.psycopg2.connect")
    def test_incident_not_found(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        result = write_incident_report.invoke({
            "incident_id": "nonexistent",
            "report_text": "test",
            "confidence_score": 0.5,
        })
        assert "찾을 수 없습니다" in result
