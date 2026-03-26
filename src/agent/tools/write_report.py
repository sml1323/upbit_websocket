import json

import psycopg2
from langchain_core.tools import tool

from src.config import get_db_dsn, setup_logging

logger = setup_logging("tool-write-report")


@tool
def write_incident_report(
    incident_id: str,
    report_text: str,
    confidence_score: float,
    news_context: str = "",
) -> str:
    """Incident에 Agent가 생성한 분석 리포트를 저장합니다.

    Args:
        incident_id: 업데이트할 incident의 UUID
        report_text: Agent가 생성한 분석 리포트 텍스트
        confidence_score: 신뢰도 점수 (0.0 ~ 1.0)
        news_context: 관련 뉴스 컨텍스트 (선택)

    Returns:
        저장 결과 메시지
    """
    query = """
        UPDATE incidents
        SET agent_report = %s,
            confidence_score = %s,
            news_context = %s,
            status = 'analyzed'
        WHERE incident_id = %s::uuid
        RETURNING incident_id
    """
    report_json = json.dumps({"text": report_text}, ensure_ascii=False)
    news_json = json.dumps({"raw": news_context}, ensure_ascii=False) if news_context else None

    try:
        conn = psycopg2.connect(get_db_dsn())
        with conn.cursor() as cur:
            cur.execute(query, (report_json, confidence_score, news_json, incident_id))
            result = cur.fetchone()
        conn.commit()
        conn.close()

        if result:
            logger.info("Incident %s 리포트 저장 완료", incident_id)
            return f"Incident {incident_id} 리포트 저장 완료 (confidence: {confidence_score:.2f})"
        else:
            return f"Incident {incident_id}를 찾을 수 없습니다."
    except Exception as e:
        logger.error("리포트 저장 실패: %s", e)
        return f"리포트 저장 실패: {e}"
