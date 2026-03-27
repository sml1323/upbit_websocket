"""Report Writer Agent — 시장분석 + 뉴스분석 종합 → 최종 리포트."""

import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.agent.tools.write_report import write_incident_report
from src.config import setup_logging

logger = setup_logging("report-agent")

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

REPORT_PROMPT = """너는 암호화폐 시장 이상 징후 리포트 작성 전문가야.
시장 분석과 뉴스 분석 결과를 종합하여 체계적인 인시던트 리포트를 작성해.

리포트에는 다음을 포함해:
- 이상 징후 요약
- 시장 데이터 분석 결과
- 뉴스 컨텍스트
- 가능한 원인 추정
- 신뢰도 점수 (0.0 ~ 1.0)

[ERROR]로 시작하는 분석 결과는 해당 분석이 실패했음을 의미해.
실패한 분석은 "해당 분석 불가"로 표시하고, 가용한 정보만으로 리포트를 작성해.

한국어로 작성하되, 간결하고 명확하게."""


def report_writer_node(state: dict) -> dict:
    """시장분석 + 뉴스분석 종합 → 리포트 작성 + DB 저장."""
    coin_code = state["anomaly"]["coin_code"]
    incident_id = state["incident_id"]
    market = state.get("market_analysis", "[ERROR] 시장 분석 없음")
    news = state.get("news_analysis", "[ERROR] 뉴스 분석 없음")

    try:
        llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0,
        )
        response = llm.invoke([
            SystemMessage(content=REPORT_PROMPT),
            HumanMessage(content=(
                f"코인: {coin_code}\n"
                f"Incident ID: {incident_id}\n\n"
                f"[앙상블 지표]\n{state.get('indicator_details', 'N/A')}\n\n"
                f"[시장 분석]\n{market}\n\n"
                f"[뉴스 분석]\n{news}\n\n"
                f"위 정보를 종합하여 인시던트 리포트를 작성하고, "
                f"write_incident_report 도구로 저장해주세요."
            )),
        ])

        report_text = response.content

        # 신뢰도 추출 (0.0~1.0)
        confidence = 0.5
        for line in report_text.split("\n"):
            if "신뢰도" in line or "confidence" in line.lower():
                import re
                match = re.search(r"(0\.\d+|1\.0)", line)
                if match:
                    confidence = float(match.group(1))
                    break

        # DB 저장
        write_incident_report.invoke({
            "incident_id": incident_id,
            "report_text": report_text,
            "confidence_score": min(max(confidence, 0.0), 1.0),
        })

        logger.info("Report Agent 완료: %s %s", coin_code, incident_id)
        return {"final_report": report_text}

    except Exception as e:
        logger.error("Report Agent 실패: %s", e)
        return {"final_report": f"[ERROR] 리포트 작성 실패: {e}"}
