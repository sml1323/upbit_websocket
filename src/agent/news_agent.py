"""News analysis node — 뉴스 검색 + 연관성 분석."""

import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.agent.tools.search_news import search_news
from src.agent.prompts import NEWS_SYSTEM_PROMPT
from src.agent.schemas import NewsEvidence
from src.config import setup_logging

logger = setup_logging("news-agent")

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5.6-luna")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def _neutral_evidence(headlines: list[str]) -> NewsEvidence:
    """판단할 기사가 없을 때의 고정 결과 — 모델을 부르지 않고 코드가 정한다."""
    return NewsEvidence(
        headlines=headlines,
        sentiment="NEUTRAL",
        relevance_score=0.0,
        source_quality="unknown",
    )


def news_analyst_node(state: dict) -> dict:
    """뉴스 검색 → (기사가 있을 때만) LLM 분석 → NewsEvidence JSON 반환."""
    coin_code = state["anomaly"]["coin_code"]

    try:
        result = search_news.invoke({"coin_code": coin_code})

        if result.status != "ok":
            # 기사가 없으면 모델이 분석할 자료가 없고 결과가 규칙으로 정해진다.
            # error 는 다른 노드 fallback 과 같은 [ERROR] 표기로 '뉴스 없음'과 구분한다 (R3 에서 상태 필드로 교체).
            headlines = ["[ERROR] 뉴스 조회 실패"] if result.status == "error" else []
            logger.info("News node LLM 생략: %s (status=%s)", coin_code, result.status)
            return {"news_analysis": _neutral_evidence(headlines).model_dump_json(ensure_ascii=False)}

        llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0,
        )
        # OpenAI Structured Outputs 로 스키마를 API 층에서 강제한다.
        # invoke() 가 NewsEvidence 인스턴스를 직접 반환한다 (.content 파싱 불필요).
        # 주의: LLM_MODEL 이 gpt-3*/gpt-4-*/gpt-4 면 langchain 이 warning 만 남기고
        #       function_calling 으로 조용히 강등한다 — 강제가 풀리므로 모델 교체 시 확인할 것.
        structured_llm = llm.with_structured_output(NewsEvidence, method="json_schema")
        evidence = structured_llm.invoke([
            SystemMessage(content=NEWS_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"코인: {coin_code}\n\n"
                f"뉴스 검색 결과:\n{result.model_dump_json(include={'articles'}, ensure_ascii=False)}\n\n"
                f"앙상블 지표:\n{state.get('indicator_details', 'N/A')}"
            )),
        ])
        logger.info("News node 분석 완료: %s (sentiment=%s)", coin_code, evidence.sentiment)
        return {"news_analysis": evidence.model_dump_json(ensure_ascii=False)}

    except Exception as e:
        # 예외 메시지에는 외부 응답 원문이 섞일 수 있어 클래스 이름만 남기고 결과에도 넣지 않는다.
        logger.error("News node 실패: %s", type(e).__name__)
        return {"news_analysis": _neutral_evidence(["[ERROR] 뉴스 분석 실패"]).model_dump_json(ensure_ascii=False)}
