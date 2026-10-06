"""뉴스 검색 도구 — 공급자 응답을 검증된 NewsSearchResult 로 정규화한다."""

import os
from collections.abc import Callable

import requests
from langchain_core.tools import tool
from pydantic import ValidationError

from src.agent.schemas import (
    MAX_NEWS_ARTICLES,
    NewsArticle,
    NewsErrorCode,
    NewsProvider,
    NewsProviderAttempt,
    NewsSearchResult,
    NewsSearchStatus,
)
from src.config import setup_logging

logger = setup_logging("tool-search-news")

CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")

# 2026-10-02 확인: 이 v1 경로는 폐기되어 404 를 준다 (현재 경로는 /api/{plan}/v2/, 유료 플랜).
# 유료 키 없이 검증할 수 없어 R1 에서는 옮기지 않는다 — docs/agent-improvement/ROADMAP.md §4 알려진 문제.
CRYPTOPANIC_URL = "https://cryptopanic.com/api/free/v1/posts/"
SERPAPI_URL = "https://serpapi.com/search.json"
REQUEST_TIMEOUT_SECONDS = 10


class _ProviderError(Exception):
    """공급자 조회 실패. 외부 원문 대신 분류만 담는다."""

    def __init__(self, error_code: NewsErrorCode, http_status: int | None = None):
        super().__init__(error_code)
        self.error_code = error_code
        self.http_status = http_status


def _get_json(url: str, params: dict) -> object:
    """GET 후 JSON 본문을 반환한다. 실패는 분류만 담은 _ProviderError 로 바꾼다.

    requests 예외 메시지에는 쿼리 문자열의 API 키가 들어 있으므로 원래 예외를 전달·기록하지 않는다(from None).
    """
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except (
        requests.Timeout
    ):  # ConnectTimeout 은 ConnectionError 이기도 해서 먼저 잡는다
        raise _ProviderError("timeout") from None
    except requests.RequestException:
        raise _ProviderError("request_error") from None
    if not 200 <= resp.status_code < 300:
        raise _ProviderError("http_error", http_status=resp.status_code)
    try:
        return resp.json()
    except ValueError:  # requests.JSONDecodeError 는 RequestException 이기도 해서 요청 예외와 따로 처리한다
        raise _ProviderError("invalid_response", http_status=resp.status_code) from None


def _text(value: object) -> str:
    """매체명처럼 없어도 되는 필드 — 문자열이 아니면 빈 문자열."""
    return value if isinstance(value, str) else ""


def _collect_articles(
    provider: NewsProvider,
    items: list,
    to_fields: Callable[[dict], dict],
) -> list[NewsArticle]:
    """항목별로 검증해 무효 항목만 뺀다. 항목이 있었는데 전부 무효면 invalid_response."""
    articles = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            articles.append(NewsArticle.model_validate(to_fields(item)))
        except ValidationError:
            continue
    dropped = len(items) - len(articles)
    if dropped:
        logger.warning("뉴스 항목 제외: provider=%s dropped=%d", provider, dropped)
    if items and not articles:
        raise _ProviderError("invalid_response")
    return articles[:MAX_NEWS_ARTICLES]


def _cryptopanic_fields(item: dict) -> dict:
    source = item.get("source")
    return {
        "title": item.get("title"),
        "url": item.get("url"),
        "source": _text(source.get("title")) if isinstance(source, dict) else "",
    }


def _serpapi_fields(item: dict) -> dict:
    return {
        "title": item.get("title"),
        "url": item.get("link"),
        "source": _text(item.get("source")),
    }


def _fetch_cryptopanic(coin_code: str) -> list[NewsArticle]:
    """CryptoPanic 뉴스. 빈 목록이면 정상 0건이고 실패는 _ProviderError 로 알린다."""
    payload = _get_json(
        CRYPTOPANIC_URL,
        {
            "auth_token": CRYPTOPANIC_API_KEY,
            "currencies": coin_code,
            "kind": "news",
            "regions": "en",
        },
    )
    items = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise _ProviderError("invalid_response")
    return _collect_articles("cryptopanic", items, _cryptopanic_fields)


def _fetch_serpapi(coin_code: str) -> list[NewsArticle]:
    """SerpAPI Google News. 결과 없음도 HTTP 200 + error 메시지로 오므로 search_metadata.status 로 판정한다."""
    payload = _get_json(
        SERPAPI_URL,
        {
            "api_key": SERPAPI_API_KEY,
            "q": f"{coin_code} 코인 뉴스",
            "tbm": "nws",
            "num": MAX_NEWS_ARTICLES,
        },
    )
    if not isinstance(payload, dict):
        raise _ProviderError("invalid_response")
    metadata = payload.get("search_metadata")
    if not isinstance(metadata, dict) or metadata.get("status") != "Success":
        raise _ProviderError("invalid_response")
    items = payload.get("news_results", [])
    if not isinstance(items, list):
        raise _ProviderError("invalid_response")
    return _collect_articles("serpapi", items, _serpapi_fields)


def _run_provider(
    provider: NewsProvider,
    api_key: str,
    fetch: Callable[[str], list[NewsArticle]],
    coin_code: str,
) -> tuple[NewsProviderAttempt, list[NewsArticle]]:
    """공급자 1곳을 확인해 시도 기록과 기사를 돌려준다. 키가 없으면 요청하지 않는다."""
    if not api_key:
        return NewsProviderAttempt(provider=provider, status="unavailable"), []
    try:
        articles = fetch(coin_code)
    except _ProviderError as e:
        logger.warning(
            "뉴스 공급자 조회 실패: provider=%s error_code=%s http_status=%s",
            provider,
            e.error_code,
            e.http_status,
        )
        return NewsProviderAttempt(
            provider=provider, status="error", error_code=e.error_code
        ), []
    return NewsProviderAttempt(
        provider=provider, status="ok" if articles else "empty"
    ), articles


def _decide_status(attempts: list[NewsProviderAttempt]) -> NewsSearchStatus:
    """공급자별 시도 기록으로 전체 상태를 정한다. 우선순위: ok > error > empty > unavailable.

    error 가 empty 보다 앞서는 이유: 일부 검색을 끝내지 못했는데 '정상적으로 0건'이라고 말하지 않기 위해서.
    """
    statuses = {attempt.status for attempt in attempts}
    for status in ("ok", "error", "empty"):
        if status in statuses:
            return status
    return "unavailable"


@tool
def search_news(coin_code: str) -> NewsSearchResult:
    """특정 코인에 대한 최신 뉴스를 검색합니다.

    CryptoPanic → SerpAPI 순서로 확인하고, 검증된 기사를 처음 얻은 공급자의 목록을 채택합니다.

    Args:
        coin_code: 코인 코드 (예: BTC, ETH)

    Returns:
        NewsSearchResult — status(ok/empty/error/unavailable), articles(title·url·source), attempts(공급자별 시도)
    """
    attempts: list[NewsProviderAttempt] = []
    articles: list[NewsArticle] = []
    # 키와 조회 함수를 호출 시점에 모듈 전역에서 읽는다 — 테스트의 patch 가 반영되게.
    for provider, api_key, fetch in (
        ("cryptopanic", CRYPTOPANIC_API_KEY, _fetch_cryptopanic),
        ("serpapi", SERPAPI_API_KEY, _fetch_serpapi),
    ):
        attempt, articles = _run_provider(provider, api_key, fetch, coin_code)
        attempts.append(attempt)
        if articles:
            break

    result = NewsSearchResult(
        status=_decide_status(attempts), articles=articles, attempts=attempts
    )
    logger.info(
        "뉴스 검색: coin=%s status=%s attempts=%s articles=%d",
        coin_code,
        result.status,
        ",".join(f"{a.provider}:{a.status}" for a in result.attempts),
        len(result.articles),
    )
    return result
