import os
from typing import TypedDict, Annotated

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from src.agent.tools.query_market import query_market_window
from src.agent.tools.search_news import search_news
from src.agent.tools.write_report import write_incident_report
from src.detector.anomaly import Anomaly
from src.config import setup_logging

logger = setup_logging("agent-graph")

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

TOOLS = [query_market_window, search_news, write_incident_report]

SYSTEM_PROMPT = """너는 암호화폐 시장 이상 감지 전문 분석가야.
이상 징후가 감지되면 다음 단계를 수행해:

1. query_market_window 도구로 해당 코인의 최근 시장 데이터를 조회
2. search_news 도구로 관련 뉴스를 검색
3. 시장 데이터와 뉴스를 종합하여 분석 리포트를 작성
4. write_incident_report 도구로 리포트를 저장

리포트에는 다음을 포함해:
- 이상 징후 요약 (어떤 코인, 어떤 유형, z-score)
- 시장 데이터 분석 (가격 변동, 거래량 변화)
- 뉴스 컨텍스트 (관련 뉴스가 있다면)
- 가능한 원인 추정
- 신뢰도 점수 (0.0 ~ 1.0)

한국어로 작성하되, 간결하고 명확하게."""


class AgentState(TypedDict):
    messages: list
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
        return {"messages": messages + [response]}

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


def analyze_anomaly(anomaly: Anomaly, incident_id: str) -> str | None:
    """이상 징후를 분석하고 리포트를 생성"""
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY가 설정되지 않음. Agent 스킵.")
        return None

    user_message = (
        f"이상 징후가 감지되었습니다:\n"
        f"- 코인: {anomaly.coin_code}\n"
        f"- 유형: {anomaly.anomaly_type}\n"
        f"- Z-score: {anomaly.z_score}\n"
        f"- 심각도: {anomaly.severity}\n"
        f"- 현재값: {anomaly.current_value:,.2f}\n"
        f"- 평균값: {anomaly.avg_value:,.2f}\n"
        f"- Incident ID: {incident_id}\n\n"
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
            "coin_code": anomaly.coin_code,
            "anomaly_type": anomaly.anomaly_type,
            "z_score": anomaly.z_score,
            "severity": anomaly.severity,
        },
        "incident_id": incident_id,
    }

    try:
        app = create_agent_graph()
        max_steps = 10
        result = app.invoke(initial_state, {"recursion_limit": max_steps})
        last_msg = result["messages"][-1]
        logger.info("Agent 분석 완료: %s %s", anomaly.coin_code, incident_id)
        return last_msg.content if hasattr(last_msg, "content") else str(last_msg)
    except Exception as e:
        logger.error("Agent 분석 실패: %s", e)
        return None
