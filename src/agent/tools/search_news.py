import os

import requests
from langchain_core.tools import tool

from src.config import setup_logging

logger = setup_logging("tool-search-news")

CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")


def _search_cryptopanic(coin_code: str) -> list[dict] | None:
    """CryptoPanic API로 뉴스 검색 (무료 tier)"""
    if not CRYPTOPANIC_API_KEY:
        return None

    url = "https://cryptopanic.com/api/free/v1/posts/"
    params = {
        "auth_token": CRYPTOPANIC_API_KEY,
        "currencies": coin_code,
        "kind": "news",
        "regions": "en",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return [
            {"title": r["title"], "url": r["url"], "source": r.get("source", {}).get("title", "")}
            for r in results[:5]
        ]
    except Exception as e:
        logger.warning("CryptoPanic 조회 실패: %s", e)
        return None


def _search_serpapi(coin_code: str) -> list[dict] | None:
    """SerpAPI 웹 검색 폴백 (한국어 뉴스 포함)"""
    if not SERPAPI_API_KEY:
        return None

    url = "https://serpapi.com/search.json"
    params = {
        "api_key": SERPAPI_API_KEY,
        "q": f"{coin_code} 코인 뉴스",
        "tbm": "nws",
        "num": 5,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("news_results", [])
        return [
            {"title": r["title"], "url": r["link"], "source": r.get("source", "")}
            for r in results[:5]
        ]
    except Exception as e:
        logger.warning("SerpAPI 조회 실패: %s", e)
        return None


@tool
def search_news(coin_code: str) -> str:
    """특정 코인에 대한 최신 뉴스를 검색합니다.

    CryptoPanic → SerpAPI 순서로 시도하고, 둘 다 실패하면 "뉴스 없음"을 반환합니다.

    Args:
        coin_code: 코인 코드 (예: BTC, ETH)

    Returns:
        뉴스 요약 문자열
    """
    # 1차: CryptoPanic
    articles = _search_cryptopanic(coin_code)

    # 2차: SerpAPI 폴백
    if not articles:
        articles = _search_serpapi(coin_code)

    # 뉴스 없음
    if not articles:
        return f"{coin_code}: 관련 뉴스를 찾을 수 없습니다."

    lines = [f"[{coin_code}] 관련 뉴스 {len(articles)}건:"]
    for i, a in enumerate(articles, 1):
        lines.append(f"{i}. {a['title']} ({a['source']})")

    return "\n".join(lines)
