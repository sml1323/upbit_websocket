"""Multi-Agent DAG — Supervisor + Sub-Agents.

Architecture:
  analyze_anomaly()
      │
      ▼
  ┌────────────┐
  │ __start__  │──── route_by_anomaly_type ──→ 조건부 분기
  └────────────┘
          │
          ├── zscore/bollinger firing → ["market_analyst", "news_analyst"] (병렬)
          └── rsi/vwap만 firing     → ["market_analyst"] (시장 분석만)
                    │                              │
                    └──────────┬───────────────────┘
                               ▼ (fan-in)
                        report_writer_node
                        (종합 리포트 작성 + DB 저장)
                               │
                               ▼
                              END
"""

import json
import os
from typing import TypedDict

import psycopg2
from langgraph.graph import StateGraph, END

from src.agent.market_agent import market_analyst_node
from src.agent.news_agent import news_analyst_node
from src.agent.report_agent import report_writer_node
from src.detector.base import EnsembleResult
from src.config import get_db_dsn, setup_logging

logger = setup_logging("agent-graph")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# 뉴스 조회가 필요한 지표 (가격/거래량 급변 → 외부 촉매 가능성)
NEWS_REQUIRED_INDICATORS = {"zscore", "bollinger_bands"}


class SupervisorState(TypedDict):
    anomaly: dict
    incident_id: str
    indicator_details: str
    market_analysis: str
    news_analysis: str
    final_report: str


def route_by_anomaly_type(state: SupervisorState) -> list[str]:
    """이상치 유형에 따라 실행할 에이전트를 결정."""
    firing = set(state["anomaly"].get("firing_indicators", []))
    if firing & NEWS_REQUIRED_INDICATORS:
        return ["market_analyst", "news_analyst"]
    return ["market_analyst"]


def build_multi_agent_graph():
    """Supervisor DAG: 조건부 fan-out → report fan-in."""
    graph = StateGraph(SupervisorState)

    graph.add_node("market_analyst", market_analyst_node)
    graph.add_node("news_analyst", news_analyst_node)
    graph.add_node("report_writer", report_writer_node)

    # 조건부 fan-out: 이상치 유형에 따라 news를 실행할지 결정
    graph.add_conditional_edges("__start__", route_by_anomaly_type)

    # fan-in: 완료된 에이전트 → report_writer
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
    """이상 징후를 멀티 에이전트로 분석하고 리포트를 생성."""
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY가 설정되지 않음. Agent 스킵.")
        return None

    firing = [s.indicator_name for s in result.signals if s.is_anomaly]

    initial_state: SupervisorState = {
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

        final_report = invoke_result.get("final_report", "")

        # 전체 에이전트 결과를 DB에 저장 (market + news + report)
        _save_agent_report(incident_id, invoke_result)

        logger.info("Multi-Agent 분석 완료: %s %s", result.coin_code, incident_id)
        return final_report if final_report else None

    except Exception as e:
        logger.error("Multi-Agent 분석 실패: %s", e)
        return None


def _save_agent_report(incident_id: str, state: dict) -> None:
    """에이전트 전체 결과를 incidents.agent_report에 저장."""
    agent_report = {
        "market_analysis": state.get("market_analysis", ""),
        "news_analysis": state.get("news_analysis", ""),
        "final_report": state.get("final_report", ""),
    }

    # final_report에서 confidence 추출
    confidence = 0.0
    try:
        report_data = json.loads(state.get("final_report", "{}"))
        confidence = float(report_data.get("confidence", 0.0))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    conn = psycopg2.connect(get_db_dsn())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE incidents
                   SET agent_report = %s,
                       confidence_score = %s,
                       status = 'analyzed'
                   WHERE incident_id = %s::uuid""",
                (json.dumps(agent_report, ensure_ascii=False), confidence, incident_id),
            )
        conn.commit()
    except Exception as e:
        logger.error("Agent report 저장 실패: %s", e)
    finally:
        conn.close()
