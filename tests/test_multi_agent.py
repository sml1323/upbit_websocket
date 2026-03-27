"""Tests for multi-agent system."""

from unittest.mock import patch, MagicMock

from src.agent.market_agent import market_analyst_node
from src.agent.news_agent import news_analyst_node
from src.agent.report_agent import report_writer_node
from src.agent.graph import build_multi_agent_graph, _format_indicator_details, SupervisorState


def _base_state():
    return {
        "messages": [],
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


class TestMarketAnalystNode:
    @patch("src.agent.market_agent.ChatOpenAI")
    @patch("src.agent.market_agent.query_market_window")
    def test_success(self, mock_tool, mock_llm_cls):
        mock_tool.invoke.return_value = "BTC: close=50000, volume=100"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="BTC 상승 추세.")
        mock_llm_cls.return_value = mock_llm

        result = market_analyst_node(_base_state())
        assert "market_analysis" in result
        assert result["market_analysis"] == "BTC 상승 추세."

    @patch("src.agent.market_agent.query_market_window")
    def test_tool_failure(self, mock_tool):
        mock_tool.invoke.side_effect = Exception("DB connection failed")

        result = market_analyst_node(_base_state())
        assert "[ERROR]" in result["market_analysis"]


class TestNewsAnalystNode:
    @patch("src.agent.news_agent.ChatOpenAI")
    @patch("src.agent.news_agent.search_news")
    def test_success(self, mock_tool, mock_llm_cls):
        mock_tool.invoke.return_value = "BTC 관련 뉴스 3건"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="규제 뉴스 영향.")
        mock_llm_cls.return_value = mock_llm

        result = news_analyst_node(_base_state())
        assert "news_analysis" in result
        assert result["news_analysis"] == "규제 뉴스 영향."

    @patch("src.agent.news_agent.search_news")
    def test_tool_failure(self, mock_tool):
        mock_tool.invoke.side_effect = Exception("API timeout")

        result = news_analyst_node(_base_state())
        assert "[ERROR]" in result["news_analysis"]


class TestReportWriterNode:
    @patch("src.agent.report_agent.write_incident_report")
    @patch("src.agent.report_agent.ChatOpenAI")
    def test_success(self, mock_llm_cls, mock_tool):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="리포트: BTC 이상감지. 신뢰도: 0.8"
        )
        mock_llm_cls.return_value = mock_llm
        mock_tool.invoke.return_value = "저장 완료"

        state = _base_state()
        state["market_analysis"] = "상승 추세"
        state["news_analysis"] = "규제 뉴스"

        result = report_writer_node(state)
        assert "final_report" in result
        assert "리포트" in result["final_report"]
        mock_tool.invoke.assert_called_once()

    @patch("src.agent.report_agent.write_incident_report")
    @patch("src.agent.report_agent.ChatOpenAI")
    def test_with_error_inputs(self, mock_llm_cls, mock_tool):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="부분 리포트. 시장 분석 불가. 신뢰도: 0.3"
        )
        mock_llm_cls.return_value = mock_llm
        mock_tool.invoke.return_value = "저장 완료"

        state = _base_state()
        state["market_analysis"] = "[ERROR] 시장 분석 실패"
        state["news_analysis"] = "뉴스 있음"

        result = report_writer_node(state)
        assert "final_report" in result

    @patch("src.agent.report_agent.ChatOpenAI")
    def test_llm_failure(self, mock_llm_cls):
        mock_llm_cls.side_effect = Exception("LLM unavailable")

        state = _base_state()
        state["market_analysis"] = "분석 결과"
        state["news_analysis"] = "뉴스"

        result = report_writer_node(state)
        assert "[ERROR]" in result["final_report"]


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
