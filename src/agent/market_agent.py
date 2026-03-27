"""Market Analyst Agent — 시장 데이터 조회 + 기술적 분석."""

import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.agent.tools.query_market import query_market_window
from src.config import setup_logging

logger = setup_logging("market-agent")

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

MARKET_PROMPT = """너는 암호화폐 시장 기술적 분석 전문가야.
OHLCV 데이터를 분석하여 다음을 파악해:
- 가격 추세 (상승/하락/횡보)
- 거래량 변화 패턴
- 주요 지지/저항 수준

간결하게 핵심만 3~5문장으로 보고해. 한국어로 작성."""


def market_analyst_node(state: dict) -> dict:
    """시장 데이터 조회 → LLM 분석 → market_analysis 반환."""
    coin_code = state["anomaly"]["coin_code"]

    try:
        market_data = query_market_window.invoke({"coin_code": coin_code, "minutes": 60})

        llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0,
        )
        response = llm.invoke([
            SystemMessage(content=MARKET_PROMPT),
            HumanMessage(content=(
                f"코인: {coin_code}\n\n"
                f"시장 데이터 (최근 60분):\n{market_data}\n\n"
                f"앙상블 지표:\n{state.get('indicator_details', 'N/A')}"
            )),
        ])

        logger.info("Market Agent 분석 완료: %s", coin_code)
        return {"market_analysis": response.content}

    except Exception as e:
        logger.error("Market Agent 실패: %s", e)
        return {"market_analysis": f"[ERROR] 시장 데이터 분석 실패: {e}"}
