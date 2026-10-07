"""E1 평가 도구 테스트 — 사례 파일 무결성, 스냅샷 주입, 집계. LLM·DB·뉴스 API 는 부르지 않는다."""

import re
from unittest.mock import MagicMock, patch

import pytest

from evals.run_eval import CASES_DIR, SnapshotTool, load_cases, run_once, summarize
from evals.scoring import AXES, rule_action, score_run
from src.agent.graph import build_analysis_workflow, route_by_anomaly_type
from src.agent.schemas import IncidentAssessment, MarketEvidence, NewsEvidence, NewsSearchResult

CASES = load_cases()


def _llm_returning(obj):
    llm = MagicMock()
    llm.with_structured_output.return_value.invoke.return_value = obj
    return MagicMock(return_value=llm)


MARKET = MarketEvidence(claim="급등", evidence=["거래 급증"], confidence=0.7, missing_data=[])
NEWS = NewsEvidence(headlines=["h"], sentiment="BULLISH", relevance_score=0.6, source_quality="major_media")
REPORT = IncidentAssessment(
    root_cause="매수 유입", confidence=0.8, supporting_evidence=["거래 급증"],
    alternative_hypotheses=[], recommended_action="ALERT", summary="요약",
)


class TestCaseFiles:
    def test_set_has_ten_cases_with_unique_ids(self):
        assert len(CASES) == 10
        assert len({c["id"] for c in CASES}) == 10

    @pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
    def test_case_is_consistent(self, case):
        # 기대 노드는 현재 라우팅 함수와 일치해야 한다 — 라우팅이 바뀌면 세트 버전을 올릴 신호
        routed = route_by_anomaly_type(case["state"])
        assert case["label"]["expected_nodes"] == [*routed, "report_writer"]
        news = case["snapshots"]["news"]
        assert (news is not None) == ("news_analyst" in routed)
        if news is not None:
            NewsSearchResult.model_validate(news)
        assert case["snapshots"]["market"].startswith(f"[{case['source']['coin_code']}]")
        label = case["label"]
        assert label["status"] in {"todo", "draft", "confirmed"}
        if label["status"] != "todo":
            assert label["recommended_action"] in {"MONITOR", "ALERT", "ESCALATE"}
            assert label["rationale"]
        # 뉴스 기사가 없으면 관련성 라벨을 달 수 없다
        if news is None or news["status"] != "ok":
            assert label["news_relevant"] is None

    def test_no_secrets_in_case_files(self):
        for path in sorted(CASES_DIR.glob("*.json")):
            text = path.read_text()
            assert "api_key" not in text and "auth_token" not in text
            assert not re.search(r"\bsk-[A-Za-z0-9_-]{20,}", text)  # 기사 URL 의 'risk-87k' 같은 단어는 통과


class TestSnapshotTool:
    def test_returns_snapshot_for_incident_coin(self):
        assert SnapshotTool("t", "BTC", "data").invoke({"coin_code": "BTC"}) == "data"

    def test_rejects_other_coin(self):
        with pytest.raises(RuntimeError, match="ETH"):
            SnapshotTool("t", "BTC", "data").invoke({"coin_code": "ETH"})

    def test_missing_snapshot_raises(self):
        with pytest.raises(RuntimeError, match="스냅샷이 없음"):
            SnapshotTool("t", "BTC", None).invoke({"coin_code": "BTC"})


class TestRunOnce:
    def _run(self, case):
        with (
            patch("src.agent.market_agent.ChatOpenAI", _llm_returning(MARKET)) as market_llm,
            patch("src.agent.news_agent.ChatOpenAI", _llm_returning(NEWS)),
            patch("src.agent.report_agent.ChatOpenAI", _llm_returning(REPORT)),
        ):
            result = run_once(build_analysis_workflow(), case)
        return result, market_llm

    def test_injects_market_snapshot_and_parses_outputs(self):
        case = next(c for c in CASES if c["id"] == "E1-01")
        result, market_llm = self._run(case)
        prompt = market_llm.return_value.with_structured_output.return_value.invoke.call_args[0][0][1].content
        assert case["snapshots"]["market"] in prompt
        assert sorted(result["nodes"]) == sorted(case["label"]["expected_nodes"])
        assert result["action"] == "ALERT" and result["confidence"] == 0.8
        assert result["relevance_score"] == 0.6
        assert result["node_errors"] == []

    def test_market_only_case_has_no_news_score(self):
        case = next(c for c in CASES if c["state"]["anomaly"]["firing_indicators"] == ["vwap"])
        result, _ = self._run(case)
        assert "news_analyst" not in result["nodes"]
        assert result["relevance_score"] is None

    def test_news_error_snapshot_is_not_a_node_error(self):
        case = next(c for c in CASES if c["snapshots"]["news"] and c["snapshots"]["news"]["status"] == "error")
        result, _ = self._run(case)
        assert result["node_errors"] == []
        assert result["relevance_score"] == 0.0  # 기사 없음은 코드가 정한 고정값

    def test_report_failure_yields_no_action(self):
        case = CASES[0]
        with (
            patch("src.agent.market_agent.ChatOpenAI", _llm_returning(MARKET)),
            patch("src.agent.news_agent.ChatOpenAI", _llm_returning(NEWS)),
            patch("src.agent.report_agent.ChatOpenAI", side_effect=Exception("boom")),
        ):
            result = run_once(build_analysis_workflow(), case)
        assert "report_writer" in result["node_errors"]
        assert result["action"] is None  # fallback 의 MONITOR 를 정답으로 세지 않는다


class TestScoringHelpers:
    @pytest.mark.parametrize("firing,expected", [
        (["vwap"], "MONITOR"),
        (["zscore", "vwap"], "ALERT"),
        (["zscore", "bollinger_bands", "vwap"], "ALERT"),
        (["zscore", "bollinger_bands", "rsi", "vwap"], "ESCALATE"),
    ])
    def test_rule_action(self, firing, expected):
        assert rule_action(firing) == expected

    LABEL = {"expected_nodes": ["market_analyst", "news_analyst", "report_writer"],
             "recommended_action": "ESCALATE", "news_relevant": False}
    FIRING = ["zscore", "bollinger_bands", "vwap"]

    def _run(self, **overrides):
        return {"nodes": ["news_analyst", "market_analyst", "report_writer"], "action": "ESCALATE",
                "relevance_score": 0.2} | overrides

    def test_score_run_all_axes(self):
        # 노드 완료 순서가 달라도 routing 은 맞음, 규칙 답(ALERT)과 분석가 답(ESCALATE)은 따로 채점
        assert score_run(self.LABEL, self.FIRING, self._run()) == {
            "routing": True, "judgment": True, "rule": False, "news": True}

    def test_score_run_report_failure_counts_as_wrong(self):
        scores = score_run(self.LABEL, self.FIRING, self._run(action=None))
        assert scores["judgment"] is False and scores["rule"] is False

    @pytest.mark.parametrize("label_rel,score,expected", [
        (None, 0.9, None),     # 기사 없는 사례는 채점 제외
        (False, None, False),  # 기사가 있는데 뉴스 판단 없음
        (True, 0.5, True),     # 경계값은 관련 있음
        (False, 0.5, False),
        (True, 0.49, False),
    ])
    def test_score_run_news_axis(self, label_rel, score, expected):
        label = self.LABEL | {"news_relevant": label_rel}
        assert score_run(label, self.FIRING, self._run(relevance_score=score))["news"] is expected

    def test_score_run_routing_mismatch(self):
        assert score_run(self.LABEL, self.FIRING, self._run(nodes=["market_analyst", "report_writer"]))["routing"] is False

    def test_summarize_ranges_and_skips_none(self):
        def rec(run, judgment, news, conf):
            scores = {axis: True for axis in AXES} | {"judgment": judgment, "news": news}
            return {"run": run, "scores": scores, "confidence": conf, "usage": {"m": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}},
                    "node_errors": [], "latency_s": 1.0}
        records = [rec(0, True, None, 0.9), rec(0, False, True, 0.5), rec(1, True, None, 0.8), rec(1, True, False, 0.7)]
        s = summarize(records, runs=2)
        assert s["judgment"]["per_run"] == [0.5, 1.0]
        assert (s["judgment"]["min"], s["judgment"]["max"]) == (0.5, 1.0)
        assert s["news"]["per_run"] == [1.0, 0.0] and s["news"]["n_cases"] == 1
        assert s["confidence"]["judgment_miss_mean"] == 0.5
        assert s["tokens"]["m"]["total_tokens"] == 60
