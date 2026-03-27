"""News Analyst Agent — 뉴스 검색 + 연관성 분석."""

import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.agent.tools.search_news import search_news
from src.config import setup_logging

logger = setup_logging("news-agent")

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

NEWS_PROMPT = """너는 암호화폐 뉴스 분석 전문가야.
뉴스를 검색하고 다음을 분석해:
- 이상 징후와 관련된 뉴스가 있는지
- 뉴스의 시장 영향 가능성
- 뉴스가 없다면 "관련 뉴스 없음"이라고 명확히 보고

간결하게 핵심만 3~5문장으로 보고해. 한국어로 작성."""


def news_analyst_node(state: dict) -> dict:
    """뉴스 검색 → LLM 분석 → news_analysis 반환."""
    coin_code = state["anomaly"]["coin_code"]

    try:
        news_data = search_news.invoke({"coin_code": coin_code})

        llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0,
        )
        response = llm.invoke([
            SystemMessage(content=NEWS_PROMPT),
            HumanMessage(content=(
                f"코인: {coin_code}\n\n"
                f"뉴스 검색 결과:\n{news_data}\n\n"
                f"앙상블 지표:\n{state.get('indicator_details', 'N/A')}"
            )),
        ])

        logger.info("News Agent 분석 완료: %s", coin_code)
        return {"news_analysis": response.content}

    except Exception as e:
        logger.error("News Agent 실패: %s", e)
        return {"news_analysis": f"[ERROR] 뉴스 분석 실패: {e}"}
