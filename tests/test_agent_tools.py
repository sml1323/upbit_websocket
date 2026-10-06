import json
import logging
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import pytest
import requests

import src.agent.tools.search_news as sn
from src.agent.news_agent import news_analyst_node
from src.agent.schemas import NewsArticle, NewsEvidence, NewsProviderAttempt
from src.agent.tools.query_market import query_market_window
from src.agent.tools.search_news import (
    _ProviderError,
    _decide_status,
    _fetch_cryptopanic,
    _fetch_serpapi,
    _get_json,
    search_news,
)


@pytest.fixture(autouse=True)
def _block_real_http(monkeypatch):
    """.env 의 실제 SerpAPI 키가 로드돼 있으므로, mock 을 빠뜨린 테스트가 진짜 요청을 보내지 않게 막는다."""
    monkeypatch.setattr(sn.requests, "get", MagicMock(side_effect=AssertionError("테스트에서 실제 HTTP 요청 금지")))


@pytest.fixture
def mock_get(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(sn.requests, "get", fake)
    return fake


def _response(status: int = 200, payload: object = None, body: str | None = None) -> requests.Response:
    """실제 requests.Response — status_code·json() 이 진짜와 같게 동작한다."""
    resp = requests.Response()
    resp.status_code = status
    resp._content = (json.dumps(payload) if body is None else body).encode("utf-8")
    resp.encoding = "utf-8"
    return resp


SERP_ITEM = {
    "title": "Bitcoin ETF inflows hit record",
    "link": "https://news.example.com/a?id=1&lang=한글",
    "source": "CoinDesk",
}
SERP_OK = {
    "search_metadata": {"status": "Success"},
    "news_results": [SERP_ITEM, {"title": "비트코인 급등", "link": "https://news.example.kr/b", "source": "한경"}],
}
SERP_NO_RESULTS = {
    "search_metadata": {"status": "Success"},
    "error": "Google hasn't returned any results for this query.",
}
CRYPTO_OK = {
    "results": [
        {"title": "BTC surges", "url": "https://cryptopanic.com/news/1/btc-surges", "source": {"title": "CoinDesk"}},
    ]
}


def _serp_payload(items: list) -> dict:
    return {"search_metadata": {"status": "Success"}, "news_results": items}


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


class TestGetJson:
    def test_returns_json_body(self, mock_get):
        mock_get.return_value = _response(200, {"a": 1})
        assert _get_json("https://x.test", {}) == {"a": 1}

    @pytest.mark.parametrize("exc, code", [
        (requests.Timeout(), "timeout"),
        (requests.ConnectTimeout(), "timeout"),  # ConnectionError 이기도 함 — timeout 이 먼저
        (requests.ConnectionError(), "request_error"),
    ])
    def test_request_failures_are_classified(self, mock_get, exc, code):
        mock_get.side_effect = exc
        with pytest.raises(_ProviderError) as info:
            _get_json("https://x.test", {})
        assert info.value.error_code == code

    def test_non_2xx_is_http_error(self, mock_get):
        mock_get.return_value = _response(429, {"error": "Your account has run out of searches."})
        with pytest.raises(_ProviderError) as info:
            _get_json("https://x.test", {})
        assert (info.value.error_code, info.value.http_status) == ("http_error", 429)

    def test_broken_json_is_invalid_response(self, mock_get):
        # requests.JSONDecodeError 는 RequestException 이기도 함 — request_error 로 새면 안 된다
        mock_get.return_value = _response(200, body="<html>not json</html>")
        with pytest.raises(_ProviderError) as info:
            _get_json("https://x.test", {})
        assert info.value.error_code == "invalid_response"


class TestFetchCryptoPanic:
    def test_parses_articles(self, mock_get):
        mock_get.return_value = _response(200, CRYPTO_OK)
        assert _fetch_cryptopanic("BTC") == [
            NewsArticle(title="BTC surges", url="https://cryptopanic.com/news/1/btc-surges", source="CoinDesk"),
        ]

    def test_empty_results_list(self, mock_get):
        mock_get.return_value = _response(200, {"results": []})
        assert _fetch_cryptopanic("BTC") == []

    @pytest.mark.parametrize("payload", [{"status": "api_error"}, {"results": {"a": 1}}, ["not", "a", "dict"]])
    def test_malformed_body_is_invalid_response(self, mock_get, payload):
        mock_get.return_value = _response(200, payload)
        with pytest.raises(_ProviderError) as info:
            _fetch_cryptopanic("BTC")
        assert info.value.error_code == "invalid_response"

    def test_retired_v1_endpoint_is_http_error(self, mock_get):
        # 2026-10-02 실측: 폐기된 /api/free/v1/ 은 404 와 api_error 본문을 준다.
        mock_get.return_value = _response(404, {"status": "api_error", "info": "Unknown API endpoint."})
        with pytest.raises(_ProviderError) as info:
            _fetch_cryptopanic("BTC")
        assert (info.value.error_code, info.value.http_status) == ("http_error", 404)


class TestFetchSerpApi:
    def test_parses_articles_and_keeps_url_string(self, mock_get):
        mock_get.return_value = _response(200, SERP_OK)
        articles = _fetch_serpapi("BTC")
        assert [a.url for a in articles] == [SERP_ITEM["link"], "https://news.example.kr/b"]
        assert articles[0].source == "CoinDesk"

    def test_no_results_message_is_empty_not_error(self, mock_get):
        mock_get.return_value = _response(200, SERP_NO_RESULTS)
        assert _fetch_serpapi("BTC") == []

    @pytest.mark.parametrize("payload", [
        {"search_metadata": {"status": "Error"}, "error": "Search failed"},
        {"news_results": [SERP_ITEM]},  # search_metadata 없음
        {"search_metadata": {"status": "Success"}, "news_results": {"a": 1}},
        ["not", "a", "dict"],
    ])
    def test_unsuccessful_or_malformed_is_invalid_response(self, mock_get, payload):
        mock_get.return_value = _response(200, payload)
        with pytest.raises(_ProviderError) as info:
            _fetch_serpapi("BTC")
        assert info.value.error_code == "invalid_response"

    def test_drops_only_invalid_items(self, mock_get):
        items = [
            {"title": "no link"},
            {"title": "bad scheme", "link": "javascript:alert(1)"},
            {"title": "   ", "link": "https://news.example.com/blank-title"},
            "not a dict",
            SERP_ITEM,
        ]
        mock_get.return_value = _response(200, _serp_payload(items))
        assert [a.title for a in _fetch_serpapi("BTC")] == [SERP_ITEM["title"]]

    def test_all_items_invalid_is_invalid_response(self, mock_get):
        mock_get.return_value = _response(200, _serp_payload([{"title": "no link"}]))
        with pytest.raises(_ProviderError) as info:
            _fetch_serpapi("BTC")
        assert info.value.error_code == "invalid_response"

    def test_caps_at_five_valid_articles(self, mock_get):
        items = [{"title": "no link"}] + [{"title": f"t{i}", "link": f"https://news.example.com/{i}"} for i in range(7)]
        mock_get.return_value = _response(200, _serp_payload(items))
        assert [a.title for a in _fetch_serpapi("BTC")] == ["t0", "t1", "t2", "t3", "t4"]

    def test_non_string_source_becomes_empty(self, mock_get):
        mock_get.return_value = _response(200, _serp_payload([{**SERP_ITEM, "source": {"name": "CoinDesk"}}]))
        assert _fetch_serpapi("BTC")[0].source == ""


ARTICLE = NewsArticle(title="BTC surges", url="https://news.example.com/a", source="CoinDesk")


def _attempts(*statuses: str) -> list[NewsProviderAttempt]:
    return [
        NewsProviderAttempt(provider=provider, status=status, error_code="timeout" if status == "error" else None)
        for provider, status in zip(("cryptopanic", "serpapi"), statuses)
    ]


class TestDecideStatus:
    @pytest.mark.parametrize("statuses, expected", [
        (("ok",), "ok"),
        (("error", "ok"), "ok"),
        (("empty", "error"), "error"),
        (("error", "unavailable"), "error"),
        (("empty", "unavailable"), "empty"),
        (("unavailable", "empty"), "empty"),
        (("unavailable", "unavailable"), "unavailable"),
    ])
    def test_priority(self, statuses, expected):
        assert _decide_status(_attempts(*statuses)) == expected


def _run_search(monkeypatch, crypto: str, serp: str):
    """두 공급자의 결과를 정해 두고 search_news 를 실행한다. outcome: ok / empty / error / unavailable."""
    fetches = {}
    for name, outcome in (("cryptopanic", crypto), ("serpapi", serp)):
        def fetch(coin_code, outcome=outcome):
            if outcome == "error":
                raise _ProviderError("timeout")
            return [ARTICLE] if outcome == "ok" else []
        fetches[name] = MagicMock(side_effect=fetch)
    monkeypatch.setattr(sn, "CRYPTOPANIC_API_KEY", "" if crypto == "unavailable" else "test-key")
    monkeypatch.setattr(sn, "SERPAPI_API_KEY", "" if serp == "unavailable" else "test-key")
    monkeypatch.setattr(sn, "_fetch_cryptopanic", fetches["cryptopanic"])
    monkeypatch.setattr(sn, "_fetch_serpapi", fetches["serpapi"])
    return search_news.invoke({"coin_code": "BTC"}), fetches


class TestSearchNews:
    @pytest.mark.parametrize("crypto, serp, status, attempts", [
        ("ok", "ok", "ok", ["cryptopanic:ok"]),
        ("error", "ok", "ok", ["cryptopanic:error", "serpapi:ok"]),
        ("unavailable", "ok", "ok", ["cryptopanic:unavailable", "serpapi:ok"]),
        ("empty", "ok", "ok", ["cryptopanic:empty", "serpapi:ok"]),
        ("empty", "empty", "empty", ["cryptopanic:empty", "serpapi:empty"]),
        ("unavailable", "unavailable", "unavailable", ["cryptopanic:unavailable", "serpapi:unavailable"]),
        ("error", "empty", "error", ["cryptopanic:error", "serpapi:empty"]),
        ("empty", "error", "error", ["cryptopanic:empty", "serpapi:error"]),
        ("error", "unavailable", "error", ["cryptopanic:error", "serpapi:unavailable"]),
        ("unavailable", "error", "error", ["cryptopanic:unavailable", "serpapi:error"]),
        ("error", "error", "error", ["cryptopanic:error", "serpapi:error"]),
        ("empty", "unavailable", "empty", ["cryptopanic:empty", "serpapi:unavailable"]),
        ("unavailable", "empty", "empty", ["cryptopanic:unavailable", "serpapi:empty"]),
    ])
    def test_status_matrix(self, monkeypatch, crypto, serp, status, attempts):
        result, _ = _run_search(monkeypatch, crypto, serp)
        assert result.status == status
        assert [f"{a.provider}:{a.status}" for a in result.attempts] == attempts
        assert result.articles == ([ARTICLE] if status == "ok" else [])

    def test_first_success_skips_second_provider(self, monkeypatch):
        _, fetches = _run_search(monkeypatch, "ok", "ok")
        fetches["serpapi"].assert_not_called()

    def test_missing_key_skips_request(self, monkeypatch):
        _, fetches = _run_search(monkeypatch, "unavailable", "ok")
        fetches["cryptopanic"].assert_not_called()

    def test_error_attempt_keeps_error_code(self, monkeypatch):
        result, _ = _run_search(monkeypatch, "error", "ok")
        assert result.attempts[0].error_code == "timeout"


class TestNoSecretLeak:
    SECRET = "SECRET-KEY-123"

    @pytest.mark.parametrize("exc", [requests.ConnectionError, requests.Timeout])
    def test_request_failure_does_not_leak_key(self, monkeypatch, mock_get, caplog, exc):
        # 실제 requests 예외처럼 메시지에 쿼리 문자열의 키를 넣는다.
        mock_get.side_effect = exc(f"Max retries exceeded with url: /search.json?api_key={self.SECRET}&q=BTC")
        monkeypatch.setattr(sn, "CRYPTOPANIC_API_KEY", "")
        monkeypatch.setattr(sn, "SERPAPI_API_KEY", self.SECRET)
        with caplog.at_level(logging.INFO):
            result = search_news.invoke({"coin_code": "BTC"})
        assert result.status == "error"
        assert "serpapi" in caplog.text  # 로그는 남긴다 — 키만 빠진다
        assert self.SECRET not in caplog.text
        assert self.SECRET not in result.model_dump_json()


class TestSearchNewsIntoNode:
    """공급자 응답 → 도구 → 뉴스 노드의 LLM 입력까지 (requests·LLM 만 mock)."""

    def test_provider_url_reaches_llm_input(self, monkeypatch, mock_get):
        mock_get.return_value = _response(200, SERP_OK)
        monkeypatch.setattr(sn, "CRYPTOPANIC_API_KEY", "")
        monkeypatch.setattr(sn, "SERPAPI_API_KEY", "test-key")
        llm = MagicMock()
        llm.with_structured_output.return_value.invoke.return_value = NewsEvidence(
            headlines=[SERP_ITEM["title"]], sentiment="BULLISH", relevance_score=0.6, source_quality="major_media",
        )
        monkeypatch.setattr("src.agent.news_agent.ChatOpenAI", MagicMock(return_value=llm))

        news_analyst_node({"anomaly": {"coin_code": "BTC"}, "indicator_details": "zscore: 5.2"})

        human = llm.with_structured_output.return_value.invoke.call_args.args[0][1].content
        # JSON 직렬화(ensure_ascii=False)로 URL 이 원래 문자열 그대로 들어간다
        assert f'"url":"{SERP_ITEM["link"]}"' in human
        assert '"url":"https://news.example.kr/b"' in human
