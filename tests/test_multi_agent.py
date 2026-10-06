"""Tests for the structured LLM analysis workflow."""

import json
import logging
from unittest.mock import patch, MagicMock

import pytest

from src.agent.market_agent import market_analyst_node
from src.agent.news_agent import news_analyst_node
from src.agent.prompts import NEWS_SYSTEM_PROMPT
from src.agent.report_agent import report_writer_node
from src.agent.graph import build_analysis_workflow, _format_indicator_details, SupervisorState
from src.agent.schemas import (
    IncidentAssessment,
    MarketEvidence,
    NewsArticle,
    NewsEvidence,
    NewsSearchResult,
)


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


MOCK_MARKET_OBJ = MarketEvidence.model_validate_json(MOCK_MARKET_JSON)
MOCK_NEWS_OBJ = NewsEvidence.model_validate_json(MOCK_NEWS_JSON)
MOCK_REPORT_OBJ = IncidentAssessment.model_validate_json(MOCK_REPORT_JSON)


def _structured_llm_mock(obj):
    """with_structured_output(...).invoke(...) 가 Pydantic 인스턴스를 반환하는 목.

    스키마 강제 전환 후 노드는 .content 를 파싱하지 않고 모델 객체를 직접 받는다.
    """
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.invoke.return_value = obj
    return mock_llm


def _assert_schema_enforced(mock_llm, schema):
    """API 층 강제가 실제로 걸렸는지 — 프롬프트 부탁으로 회귀하면 여기서 잡힌다."""
    mock_llm.with_structured_output.assert_called_once_with(
        schema, method="json_schema"
    )
    mock_llm.invoke.assert_not_called()


class TestMarketAnalystNode:
    @patch("src.agent.market_agent.ChatOpenAI")
    @patch("src.agent.market_agent.query_market_window")
    def test_success(self, mock_tool, mock_llm_cls):
        mock_tool.invoke.return_value = "BTC: close=50000, volume=100"
        mock_llm = _structured_llm_mock(MOCK_MARKET_OBJ)
        mock_llm_cls.return_value = mock_llm

        result = market_analyst_node(_base_state())
        _assert_schema_enforced(mock_llm, MarketEvidence)
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


NEWS_ARTICLE = NewsArticle(
    title="BTC ETF 승인 임박 보도",
    url="https://news.example.com/etf?id=1&lang=한글",
    source="CoinDesk",
)
NEWS_OK = NewsSearchResult(
    status="ok",
    articles=[NEWS_ARTICLE],
    attempts=[
        {"provider": "cryptopanic", "status": "unavailable"},
        {"provider": "serpapi", "status": "ok"},
    ],
)


def _human_message(mock_llm) -> str:
    """structured LLM 에 전달된 HumanMessage 본문."""
    messages = mock_llm.with_structured_output.return_value.invoke.call_args.args[0]
    return messages[1].content


class TestNewsAnalystNode:
    @patch("src.agent.news_agent.ChatOpenAI")
    @patch("src.agent.news_agent.search_news")
    def test_success(self, mock_tool, mock_llm_cls):
        mock_tool.invoke.return_value = NEWS_OK
        mock_llm = _structured_llm_mock(MOCK_NEWS_OBJ)
        mock_llm_cls.return_value = mock_llm

        result = news_analyst_node(_base_state())
        _assert_schema_enforced(mock_llm, NewsEvidence)
        assert "news_analysis" in result
        evidence = NewsEvidence.model_validate_json(result["news_analysis"])
        assert evidence.sentiment == "BULLISH"

    @patch("src.agent.news_agent.ChatOpenAI")
    @patch("src.agent.news_agent.search_news")
    def test_llm_input_is_article_json_with_url(self, mock_tool, mock_llm_cls):
        mock_tool.invoke.return_value = NEWS_OK
        mock_llm = _structured_llm_mock(MOCK_NEWS_OBJ)
        mock_llm_cls.return_value = mock_llm

        news_analyst_node(_base_state())
        human = _human_message(mock_llm)
        news_json = human.split("뉴스 검색 결과:\n", 1)[1].split("\n\n앙상블 지표:", 1)[0]
        # 상태·시도 이력은 넣지 않고 기사 목록만, URL 은 원래 문자열 그대로
        assert json.loads(news_json) == {"articles": [NEWS_ARTICLE.model_dump()]}
        assert NEWS_ARTICLE.url in human  # ensure_ascii=False — 한글이 이스케이프되지 않음
        assert "zscore: 5.2" in human  # 앙상블 지표 입력은 기존과 같다

    @pytest.mark.parametrize("status, attempt, headlines", [
        ("error", {"provider": "serpapi", "status": "error", "error_code": "timeout"}, ["[ERROR] 뉴스 조회 실패"]),
        ("empty", {"provider": "serpapi", "status": "empty"}, []),
        ("unavailable", {"provider": "serpapi", "status": "unavailable"}, []),
    ])
    def test_no_articles_skips_llm(self, status, attempt, headlines):
        with patch("src.agent.news_agent.search_news") as mock_tool, \
             patch("src.agent.news_agent.ChatOpenAI") as mock_llm_cls:
            mock_tool.invoke.return_value = NewsSearchResult(status=status, attempts=[attempt])
            result = news_analyst_node(_base_state())

        mock_llm_cls.assert_not_called()
        evidence = NewsEvidence.model_validate_json(result["news_analysis"])
        assert evidence.headlines == headlines
        assert (evidence.sentiment, evidence.relevance_score, evidence.source_quality) == (
            "NEUTRAL", 0.0, "unknown",
        )

    @patch("src.agent.news_agent.search_news")
    def test_tool_failure(self, mock_tool):
        mock_tool.invoke.side_effect = Exception("API timeout url=/search.json?api_key=SECRET")

        result = news_analyst_node(_base_state())
        evidence = NewsEvidence.model_validate_json(result["news_analysis"])
        assert evidence.sentiment == "NEUTRAL"
        assert evidence.relevance_score == 0.0
        assert evidence.headlines == ["[ERROR] 뉴스 분석 실패"]
        assert "SECRET" not in result["news_analysis"]

    def test_llm_failure_hides_exception_text(self, caplog):
        with patch("src.agent.news_agent.search_news") as mock_tool, \
             patch("src.agent.news_agent.ChatOpenAI", side_effect=Exception("upstream said: sk-SECRET")):
            mock_tool.invoke.return_value = NEWS_OK
            with caplog.at_level(logging.INFO):
                result = news_analyst_node(_base_state())

        evidence = NewsEvidence.model_validate_json(result["news_analysis"])
        assert evidence.headlines == ["[ERROR] 뉴스 분석 실패"]
        assert "sk-SECRET" not in result["news_analysis"]
        assert "sk-SECRET" not in caplog.text

    def test_prompt_describes_json_input_without_no_news_rule(self):
        assert "articles" in NEWS_SYSTEM_PROMPT and "url" in NEWS_SYSTEM_PROMPT
        assert "뉴스가 없으면" not in NEWS_SYSTEM_PROMPT  # 기사 0건은 코드가 처리한다


class TestReportWriterNode:
    @patch("src.agent.report_agent.ChatOpenAI")
    def test_success(self, mock_llm_cls):
        mock_llm = _structured_llm_mock(MOCK_REPORT_OBJ)
        mock_llm_cls.return_value = mock_llm

        state = _base_state()
        state["market_analysis"] = MOCK_MARKET_JSON
        state["news_analysis"] = MOCK_NEWS_JSON

        result = report_writer_node(state)
        _assert_schema_enforced(mock_llm, IncidentAssessment)
        assert "final_report" in result
        assessment = IncidentAssessment.model_validate_json(result["final_report"])
        assert assessment.confidence == 0.8
        assert assessment.recommended_action == "ALERT"

    @patch("src.agent.report_agent.ChatOpenAI")
    def test_with_error_inputs(self, mock_llm_cls):
        mock_llm = _structured_llm_mock(MOCK_REPORT_OBJ)
        mock_llm_cls.return_value = mock_llm

        state = _base_state()
        state["market_analysis"] = "[ERROR] 시장 분석 실패"
        state["news_analysis"] = MOCK_NEWS_JSON

        result = report_writer_node(state)
        _assert_schema_enforced(mock_llm, IncidentAssessment)
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


class TestBuildAnalysisWorkflow:
    def test_compiles(self):
        graph = build_analysis_workflow()
        assert graph is not None

    def test_has_expected_nodes(self):
        graph = build_analysis_workflow()
        node_names = set(graph.get_graph().nodes.keys())
        assert "market_analyst" in node_names
        assert "news_analyst" in node_names
        assert "report_writer" in node_names


class TestConditionalRouting:
    """조건부 라우팅 테스트."""

    def test_zscore_fires_both_nodes(self):
        from src.agent.graph import route_by_anomaly_type
        state = _base_state()
        state["anomaly"]["firing_indicators"] = ["zscore", "rsi"]
        nodes = route_by_anomaly_type(state)
        assert "market_analyst" in nodes
        assert "news_analyst" in nodes

    def test_rsi_only_fires_market_only(self):
        from src.agent.graph import route_by_anomaly_type
        state = _base_state()
        state["anomaly"]["firing_indicators"] = ["rsi", "vwap"]
        nodes = route_by_anomaly_type(state)
        assert nodes == ["market_analyst"]


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
