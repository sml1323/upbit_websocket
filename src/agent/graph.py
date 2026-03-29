"""Multi-Agent DAG — Supervisor + Sub-Agents.

Architecture:
  analyze_anomaly()
      │
      ▼
  ┌────────────┐
  │ __start__  │──── conditional_edges ──→ ["market_analyst", "news_analyst"]
  └────────────┘                            (fan-out: 병렬 실행)
                                             │              │
                                    ┌────────┘              └────────┐
                                    ▼                                ▼
                             market_analyst_node              news_analyst_node
                             (시장 데이터 조회+분석)          (뉴스 검색+분석)
                                    │                                │
                                    └──────────┬─────────────────────┘
                                               ▼ (fan-in: dict merge)
                                        report_writer_node
                                        (종합 리포트 작성+DB 저장)
                                               │
                                               ▼
                                              END
"""

import os
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from src.agent.market_agent import market_analyst_node
from src.agent.news_agent import news_analyst_node
from src.agent.report_agent import report_writer_node
from src.detector.base import EnsembleResult
from src.config import setup_logging

logger = setup_logging("agent-graph")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


class SupervisorState(TypedDict):
    messages: Annotated[list, add_messages]
    anomaly: dict
    incident_id: str
    indicator_details: str
    market_analysis: str
    news_analysis: str
    final_report: str


def build_multi_agent_graph():
    """Supervisor DAG: market + news 병렬 → report fan-in."""
    graph = StateGraph(SupervisorState)

    graph.add_node("market_analyst", market_analyst_node)
    graph.add_node("news_analyst", news_analyst_node)
    graph.add_node("report_writer", report_writer_node)

    # fan-out: __start__ → 병렬 실행
    graph.add_conditional_edges(
        "__start__",
        lambda _: ["market_analyst", "news_analyst"],
    )

    # fan-in: 둘 다 완료 → report_writer
    graph.add_edge("market_analyst", "report_writer")
    graph.add_edge("news_analyst", "report_writer")
    graph.add_edge("report_writer", END)

    return graph.compile()


def _format_indicator_details(result: EnsembleResult) -> str:
    """Format indicator signals for agent context."""
    lines = []
    for signal in result.signals:
        if not signal.ready:
            lines.append(f"  - {signal.indicator_name}: 데이터 부족 (skip)")
            continue
        status = "⚠️ 이상" if signal.is_anomaly else "✅ 정상"
        detail_str = ", ".join(f"{k}={v}" for k, v in signal.detail.items())
        lines.append(f"  - {signal.indicator_name}: {signal.value} [{status}] ({detail_str})")
    return "\n".join(lines)


def analyze_anomaly(result: EnsembleResult, incident_id: str) -> str | None:
    """이상 징후를 멀티 에이전트로 분석하고 리포트를 생성.

    인터페이스는 이전 단일 Agent와 동일. 내부만 DAG로 변경.
    """
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY가 설정되지 않음. Agent 스킵.")
        return None

    firing = [s.indicator_name for s in result.signals if s.is_anomaly]

    initial_state: SupervisorState = {
        "messages": [],
        "anomaly": {
            "coin_code": result.coin_code,
            "anomaly_type": "ensemble",
            "ensemble_score": result.ensemble_score,
            "severity": result.severity,
            "firing_indicators": firing,
        },
        "incident_id": incident_id,
        "indicator_details": _format_indicator_details(result),
        "market_analysis": "",
        "news_analysis": "",
        "final_report": "",
    }

    try:
        app = build_multi_agent_graph()
        invoke_result = app.invoke(initial_state, {"recursion_limit": 10})

        # 각 Agent 응답을 구조화하여 DB에 저장
        import json
        import psycopg2
        from src.config import get_db_dsn

        agent_report = {
            "market_analysis": invoke_result.get("market_analysis", ""),
            "news_analysis": invoke_result.get("news_analysis", ""),
            "final_report": invoke_result.get("final_report", ""),
            "indicator_details": initial_state["indicator_details"],
        }

        conn = psycopg2.connect(get_db_dsn())
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE incidents SET agent_report = %s WHERE incident_id = %s",
                    (json.dumps(agent_report, ensure_ascii=False), incident_id),
                )
            conn.commit()
        finally:
            conn.close()

        final_report = invoke_result.get("final_report", "")
        logger.info("Multi-Agent 분석 완료: %s %s", result.coin_code, incident_id)
        return final_report if final_report else None

    except Exception as e:
        logger.error("Multi-Agent 분석 실패: %s", e)
        return None
