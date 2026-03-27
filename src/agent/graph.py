import os
from typing import TypedDict, Annotated

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.agent.tools.query_market import query_market_window
from src.agent.tools.search_news import search_news
from src.agent.tools.write_report import write_incident_report
from src.detector.base import EnsembleResult
from src.config import setup_logging

logger = setup_logging("agent-graph")

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

TOOLS = [query_market_window, search_news, write_incident_report]

SYSTEM_PROMPT = """너는 암호화폐 시장 이상 감지 전문 분석가야.
앙상블 이상 감지 시스템이 여러 지표(Z-Score, Bollinger Bands, RSI, VWAP)를
동시에 분석하여 이상 징후를 감지했어. 다음 단계를 수행해:

1. query_market_window 도구로 해당 코인의 최근 시장 데이터를 조회
2. search_news 도구로 관련 뉴스를 검색
3. 시장 데이터와 뉴스를 종합하여 분석 리포트를 작성
4. write_incident_report 도구로 리포트를 저장

리포트에는 다음을 포함해:
- 이상 징후 요약 (어떤 코인, 어떤 지표들이 동시에 발화했는지)
- 각 지표별 분석 (Z-Score, BB %B, RSI, VWAP 이탈률 등)
- 시장 데이터 분석 (가격 변동, 거래량 변화)
- 뉴스 컨텍스트 (관련 뉴스가 있다면)
- 가능한 원인 추정
- 신뢰도 점수 (0.0 ~ 1.0)

한국어로 작성하되, 간결하고 명확하게."""


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    anomaly: dict
    incident_id: str


def create_agent_graph():
    """LangGraph 기반 Agent 워크플로우 생성"""
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )
    llm_with_tools = llm.bind_tools(TOOLS)

    def call_model(state: AgentState) -> dict:
        messages = state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    tool_node = ToolNode(TOOLS)

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


def _format_indicator_details(result: EnsembleResult) -> str:
    """Format indicator signals for the agent's user message."""
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
    """이상 징후를 분석하고 리포트를 생성"""
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY가 설정되지 않음. Agent 스킵.")
        return None

    firing = [s.indicator_name for s in result.signals if s.is_anomaly]

    user_message = (
        f"앙상블 이상 감지 시스템이 이상 징후를 감지했습니다:\n"
        f"- 코인: {result.coin_code}\n"
        f"- Ensemble Score: {result.ensemble_score}\n"
        f"- 심각도: {result.severity}\n"
        f"- 발화 지표 ({result.firing_count}개): {', '.join(firing)}\n"
        f"- 활성 지표: {result.active_indicator_count}개\n"
        f"- Incident ID: {incident_id}\n\n"
        f"지표별 상세:\n{_format_indicator_details(result)}\n\n"
        f"위 정보를 바탕으로 시장 데이터를 조회하고, 뉴스를 검색하고, "
        f"분석 리포트를 작성하여 저장해주세요."
    )

    from langchain_core.messages import SystemMessage, HumanMessage

    initial_state: AgentState = {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ],
        "anomaly": {
            "coin_code": result.coin_code,
            "anomaly_type": "ensemble",
            "ensemble_score": result.ensemble_score,
            "severity": result.severity,
            "firing_indicators": firing,
        },
        "incident_id": incident_id,
    }

    try:
        app = create_agent_graph()
        max_steps = 10
        invoke_result = app.invoke(initial_state, {"recursion_limit": max_steps})
        last_msg = invoke_result["messages"][-1]
        logger.info("Agent 분석 완료: %s %s", result.coin_code, incident_id)
        return last_msg.content if hasattr(last_msg, "content") else str(last_msg)
    except Exception as e:
        logger.error("Agent 분석 실패: %s", e)
        return None
