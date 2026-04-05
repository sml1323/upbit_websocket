"""Tests for multi-agent system."""

import json
from unittest.mock import patch, MagicMock

from src.agent.market_agent import market_analyst_node
from src.agent.news_agent import news_analyst_node
from src.agent.report_agent import report_writer_node
from src.agent.graph import build_multi_agent_graph, _format_indicator_details, SupervisorState
from src.agent.schemas import MarketEvidence, NewsEvidence, IncidentAssessment


def _base_state():
    return {
        "anomaly": {
            "coin_code": "BTC",
            "anomaly_type": "ensemble",
            "ensemble_score": 0.85,
            "severity": "high",
            "firing_indicators": ["zscore", "rsi"],
        },
        "incident_id": "test-inc-123",
        "indicator_details": "zscore: 5.2, rsi: 82",
        "market_analysis": "",
        "news_analysis": "",
        "final_report": "",
    }


# -- Mock JSON responses matching Pydantic schemas --

MOCK_MARKET_JSON = json.dumps({
    "claim": "BTC 30분간 5% 급등, 거래량 동반 상승",
    "evidence": ["1분봉 거래량 평균 대비 3배", "종가 기준 연속 상승"],
    "confidence": 0.85,
    "missing_data": [],
}, ensure_ascii=False)

MOCK_NEWS_JSON = json.dumps({
    "headlines": ["BTC ETF 승인 임박 보도"],
    "sentiment": "BULLISH",
    "relevance_score": 0.7,
    "source_quality": "major_media",
}, ensure_ascii=False)

MOCK_REPORT_JSON = json.dumps({
    "root_cause": "BTC ETF 승인 기대감에 따른 매수 유입",
    "confidence": 0.8,
    "supporting_evidence": ["거래량 3배 증가", "ETF 관련 뉴스 확인"],
    "alternative_hypotheses": ["고래 매집 가능성 — 단일 대량 거래 미확인으로 배제"],
    "recommended_action": "ALERT",
    "summary": "BTC에서 앙상블 이상 감지. 거래량 급증과 ETF 승인 뉴스가 동시 발생. 신뢰도 0.8.",
}, ensure_ascii=False)


class TestMarketAnalystNode:
    @patch("src.agent.market_agent.ChatOpenAI")
    @patch("src.agent.market_agent.query_market_window")
    def test_success(self, mock_tool, mock_llm_cls):
        mock_tool.invoke.return_value = "BTC: close=50000, volume=100"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=MOCK_MARKET_JSON)
        mock_llm_cls.return_value = mock_llm

        result = market_analyst_node(_base_state())
        assert "market_analysis" in result
        evidence = MarketEvidence.model_validate_json(result["market_analysis"])
        assert evidence.confidence == 0.85
        assert len(evidence.evidence) > 0

    @patch("src.agent.market_agent.query_market_window")
    def test_tool_failure(self, mock_tool):
        mock_tool.invoke.side_effect = Exception("DB connection failed")

        result = market_analyst_node(_base_state())
        evidence = MarketEvidence.model_validate_json(result["market_analysis"])
        assert evidence.confidence == 0.0
        assert "실패" in evidence.claim


class TestNewsAnalystNode:
    @patch("src.agent.news_agent.ChatOpenAI")
    @patch("src.agent.news_agent.search_news")
    def test_success(self, mock_tool, mock_llm_cls):
        mock_tool.invoke.return_value = "BTC 관련 뉴스 3건"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=MOCK_NEWS_JSON)
        mock_llm_cls.return_value = mock_llm

        result = news_analyst_node(_base_state())
        assert "news_analysis" in result
        evidence = NewsEvidence.model_validate_json(result["news_analysis"])
        assert evidence.sentiment == "BULLISH"

    @patch("src.agent.news_agent.search_news")
    def test_tool_failure(self, mock_tool):
        mock_tool.invoke.side_effect = Exception("API timeout")

        result = news_analyst_node(_base_state())
        evidence = NewsEvidence.model_validate_json(result["news_analysis"])
        assert evidence.sentiment == "NEUTRAL"
        assert evidence.relevance_score == 0.0


class TestReportWriterNode:
    @patch("src.agent.report_agent.write_incident_report")
    @patch("src.agent.report_agent.ChatOpenAI")
    def test_success(self, mock_llm_cls, mock_tool):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=MOCK_REPORT_JSON)
        mock_llm_cls.return_value = mock_llm
        mock_tool.invoke.return_value = "저장 완료"

        state = _base_state()
        state["market_analysis"] = MOCK_MARKET_JSON
        state["news_analysis"] = MOCK_NEWS_JSON

        result = report_writer_node(state)
        assert "final_report" in result
        assessment = IncidentAssessment.model_validate_json(result["final_report"])
        assert assessment.confidence == 0.8
        assert assessment.recommended_action == "ALERT"
        mock_tool.invoke.assert_called_once()

    @patch("src.agent.report_agent.write_incident_report")
    @patch("src.agent.report_agent.ChatOpenAI")
    def test_with_error_inputs(self, mock_llm_cls, mock_tool):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=MOCK_REPORT_JSON)
        mock_llm_cls.return_value = mock_llm
        mock_tool.invoke.return_value = "저장 완료"

        state = _base_state()
        state["market_analysis"] = "[ERROR] 시장 분석 실패"
        state["news_analysis"] = MOCK_NEWS_JSON

        result = report_writer_node(state)
        assert "final_report" in result

    @patch("src.agent.report_agent.ChatOpenAI")
    def test_llm_failure(self, mock_llm_cls):
        mock_llm_cls.side_effect = Exception("LLM unavailable")

        state = _base_state()
        state["market_analysis"] = MOCK_MARKET_JSON
        state["news_analysis"] = MOCK_NEWS_JSON

        result = report_writer_node(state)
        assessment = IncidentAssessment.model_validate_json(result["final_report"])
        assert assessment.confidence == 0.0
        assert "실패" in assessment.summary


class TestBuildMultiAgentGraph:
    def test_compiles(self):
        graph = build_multi_agent_graph()
        assert graph is not None

    def test_has_expected_nodes(self):
        graph = build_multi_agent_graph()
        node_names = set(graph.get_graph().nodes.keys())
        assert "market_analyst" in node_names
        assert "news_analyst" in node_names
        assert "report_writer" in node_names


class TestConditionalRouting:
    """조건부 라우팅 테스트."""

    def test_zscore_fires_both_agents(self):
        from src.agent.graph import route_by_anomaly_type
        state = _base_state()
        state["anomaly"]["firing_indicators"] = ["zscore", "rsi"]
        agents = route_by_anomaly_type(state)
        assert "market_analyst" in agents
        assert "news_analyst" in agents

    def test_rsi_only_fires_market_only(self):
        from src.agent.graph import route_by_anomaly_type
        state = _base_state()
        state["anomaly"]["firing_indicators"] = ["rsi", "vwap"]
        agents = route_by_anomaly_type(state)
        assert agents == ["market_analyst"]


class TestFormatIndicatorDetails:
    def test_formats_signals(self):
        from src.detector.base import Signal
        from src.detector.base import EnsembleResult

        signals = [
            Signal(indicator_name="zscore", coin_code="BTC", value=5.2,
                   is_anomaly=True, severity="high", detail={"price_zscore": 5.2}),
            Signal(indicator_name="rsi", coin_code="BTC", value=82.0,
                   is_anomaly=True, severity="medium", detail={"rsi_value": 82.0}),
        ]
        result = EnsembleResult(
            coin_code="BTC", is_anomaly=True, ensemble_score=0.85,
            firing_count=2, signals=signals, severity="medium",
            active_indicator_count=2,
        )
        formatted = _format_indicator_details(result)
        assert "zscore" in formatted
        assert "rsi" in formatted
        assert "이상" in formatted
