"""Market Analyst Agent — 시장 데이터 조회 + 기술적 분석."""

import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.agent.tools.query_market import query_market_window
from src.agent.prompts import MARKET_SYSTEM_PROMPT
from src.agent.schemas import MarketEvidence
from src.config import setup_logging

logger = setup_logging("market-agent")

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def market_analyst_node(state: dict) -> dict:
    """시장 데이터 조회 → LLM 분석 → MarketEvidence JSON 반환."""
    coin_code = state["anomaly"]["coin_code"]

    try:
        market_data = query_market_window.invoke({"coin_code": coin_code, "minutes": 60})

        llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0,
        )
        response = llm.invoke([
            SystemMessage(content=MARKET_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"코인: {coin_code}\n\n"
                f"시장 데이터 (최근 60분):\n{market_data}\n\n"
                f"앙상블 지표:\n{state.get('indicator_details', 'N/A')}"
            )),
        ])

        # JSON 파싱 + 스키마 검증
        evidence = MarketEvidence.model_validate_json(response.content)
        logger.info("Market Agent 분석 완료: %s (confidence=%.2f)", coin_code, evidence.confidence)
        return {"market_analysis": evidence.model_dump_json(ensure_ascii=False)}

    except Exception as e:
        logger.error("Market Agent 실패: %s", e)
        fallback = MarketEvidence(
            claim=f"[ERROR] 시장 데이터 분석 실패: {e}",
            evidence=[],
            confidence=0.0,
            missing_data=["전체 시장 데이터"],
        )
        return {"market_analysis": fallback.model_dump_json(ensure_ascii=False)}
