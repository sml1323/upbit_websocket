"""뉴스 검색 도구 반환 계약(R1) — 기사·시도·결과의 검증 규칙."""

import pytest
from pydantic import ValidationError

from src.agent.schemas import NewsArticle, NewsProviderAttempt, NewsSearchResult

ARTICLE = {"title": "BTC surges", "url": "https://news.example.com/a", "source": "CoinDesk"}


class TestNewsArticle:
    def test_keeps_url_string_as_given(self):
        # HttpUrl 이었다면 '/' 추가·퍼센트 인코딩·호스트 소문자화가 일어난다.
        raw = "https://News.Example.com/a b?q=한글"
        assert NewsArticle(title="t", url=f"  {raw}  ").url == raw

    @pytest.mark.parametrize("url", ["ftp://x.com/f", "javascript:alert(1)", "example.com/x", "https://", "http://[::1"])
    def test_rejects_non_http_url(self, url):
        with pytest.raises(ValidationError):
            NewsArticle(title="t", url=url)

    @pytest.mark.parametrize("field", ["title", "url"])
    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_rejects_missing_required_field(self, field, value):
        with pytest.raises(ValidationError):
            NewsArticle(**{**ARTICLE, field: value})

    def test_source_defaults_to_empty(self):
        assert NewsArticle(title="t", url="https://x.com").source == ""


class TestNewsProviderAttempt:
    def test_error_requires_error_code(self):
        with pytest.raises(ValidationError):
            NewsProviderAttempt(provider="serpapi", status="error")

    @pytest.mark.parametrize("status", ["ok", "empty", "unavailable"])
    def test_non_error_rejects_error_code(self, status):
        with pytest.raises(ValidationError):
            NewsProviderAttempt(provider="serpapi", status=status, error_code="timeout")

    def test_unknown_values_rejected(self):
        with pytest.raises(ValidationError):
            NewsProviderAttempt(provider="serpapi", status="error", error_code="boom")
        with pytest.raises(ValidationError):
            NewsProviderAttempt(provider="google", status="ok")


class TestNewsSearchResult:
    def test_ok_requires_articles(self):
        with pytest.raises(ValidationError):
            NewsSearchResult(status="ok", articles=[])

    @pytest.mark.parametrize("status", ["empty", "error", "unavailable"])
    def test_non_ok_rejects_articles(self, status):
        with pytest.raises(ValidationError):
            NewsSearchResult(status=status, articles=[ARTICLE])

    def test_caps_articles_at_five(self):
        with pytest.raises(ValidationError):
            NewsSearchResult(status="ok", articles=[ARTICLE] * 6)

    def test_json_keeps_url_and_attempt_order(self):
        result = NewsSearchResult(
            status="ok",
            articles=[ARTICLE],
            attempts=[
                {"provider": "cryptopanic", "status": "unavailable"},
                {"provider": "serpapi", "status": "ok"},
            ],
        )
        data = result.model_dump(mode="json")
        assert data["articles"][0]["url"] == ARTICLE["url"]
        assert [a["provider"] for a in data["attempts"]] == ["cryptopanic", "serpapi"]
