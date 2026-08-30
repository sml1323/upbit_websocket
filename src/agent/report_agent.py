"""Report synthesis node — 시장분석 + 뉴스분석 종합 → 최종 리포트."""

import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.agent.prompts import REPORT_SYSTEM_PROMPT
from src.agent.schemas import IncidentAssessment
from src.config import setup_logging

logger = setup_logging("report-agent")

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def report_writer_node(state: dict) -> dict:
    """시장분석 + 뉴스분석 종합 → IncidentAssessment JSON 반환. DB 저장은 graph.py에서 수행."""
    coin_code = state["anomaly"]["coin_code"]
    incident_id = state["incident_id"]
    market = state.get("market_analysis", '{"claim":"시장 분석 없음","evidence":[],"confidence":0.0,"missing_data":["전체"]}')
    news = state.get("news_analysis", '{"headlines":[],"sentiment":"NEUTRAL","relevance_score":0.0,"source_quality":"unknown"}')

    try:
        llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0,
        )
        # OpenAI Structured Outputs 로 스키마를 API 층에서 강제한다.
        # invoke() 가 IncidentAssessment 인스턴스를 직접 반환한다 (.content 파싱 불필요).
        # 주의: LLM_MODEL 이 gpt-3*/gpt-4-*/gpt-4 면 langchain 이 warning 만 남기고
        #       function_calling 으로 조용히 강등한다 — 강제가 풀리므로 모델 교체 시 확인할 것.
        structured_llm = llm.with_structured_output(
            IncidentAssessment, method="json_schema"
        )
        assessment = structured_llm.invoke([
            SystemMessage(content=REPORT_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"코인: {coin_code}\n"
                f"Incident ID: {incident_id}\n"
                f"Firing indicators: {state['anomaly'].get('firing_indicators', [])}\n"
                f"Severity: {state['anomaly'].get('severity', 'unknown')}\n\n"
                f"[앙상블 지표]\n{state.get('indicator_details', 'N/A')}\n\n"
                f"[시장 분석 (JSON)]\n{market}\n\n"
                f"[뉴스 분석 (JSON)]\n{news}"
            )),
        ])

        logger.info("Report node 완료: %s %s (confidence=%.2f)", coin_code, incident_id, assessment.confidence)
        return {"final_report": assessment.model_dump_json(ensure_ascii=False)}

    except Exception as e:
        logger.error("Report node 실패: %s", e)
        fallback = IncidentAssessment(
            root_cause=f"[ERROR] 리포트 작성 실패: {e}",
            confidence=0.0,
            supporting_evidence=[],
            alternative_hypotheses=[],
            recommended_action="MONITOR",
            summary=f"[ERROR] {coin_code} 인시던트 분석 실패: {e}",
        )
        return {"final_report": fallback.model_dump_json(ensure_ascii=False)}
