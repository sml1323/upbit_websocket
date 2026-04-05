"""News Analyst Agent — 뉴스 검색 + 연관성 분석."""

import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.agent.tools.search_news import search_news
from src.agent.prompts import NEWS_SYSTEM_PROMPT
from src.agent.schemas import NewsEvidence
from src.config import setup_logging

logger = setup_logging("news-agent")

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def news_analyst_node(state: dict) -> dict:
    """뉴스 검색 → LLM 분석 → NewsEvidence JSON 반환."""
    coin_code = state["anomaly"]["coin_code"]

    try:
        news_data = search_news.invoke({"coin_code": coin_code})

        llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0,
        )
        response = llm.invoke([
            SystemMessage(content=NEWS_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"코인: {coin_code}\n\n"
                f"뉴스 검색 결과:\n{news_data}\n\n"
                f"앙상블 지표:\n{state.get('indicator_details', 'N/A')}"
            )),
        ])

        # JSON 파싱 + 스키마 검증
        evidence = NewsEvidence.model_validate_json(response.content)
        logger.info("News Agent 분석 완료: %s (sentiment=%s)", coin_code, evidence.sentiment)
        return {"news_analysis": evidence.model_dump_json(ensure_ascii=False)}

    except Exception as e:
        logger.error("News Agent 실패: %s", e)
        fallback = NewsEvidence(
            headlines=[f"[ERROR] 뉴스 검색 실패: {e}"],
            sentiment="NEUTRAL",
            relevance_score=0.0,
            source_quality="unknown",
        )
        return {"news_analysis": fallback.model_dump_json(ensure_ascii=False)}
