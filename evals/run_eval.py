"""E1 평가 실행기 — 도구 자리에 스냅샷을 끼우고 실제 LLM 으로 그래프를 N회 실행해 채점한다.

    uv run python -m evals.run_eval                          # 전체 사례 × 3회
    uv run python -m evals.run_eval --cases E1-01 --runs 1   # 일부만

외부 호출은 OpenAI 뿐이다. DB 접속과 뉴스 HTTP 요청은 막아 두어, 호출되면 해당 노드가 [ERROR] 로 실패한다.
결과는 evals/results/<UTC 시각>_<커밋>.json 에 실행별 원시 출력·채점·토큰과 함께 남는다.
"""

import argparse
import copy
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from unittest.mock import patch

from langchain_core.callbacks import get_usage_metadata_callback

from evals.scoring import AXES, score_run
from src.agent import market_agent
from src.agent.graph import build_analysis_workflow
from src.agent.schemas import NewsSearchResult

EVALS_DIR = Path(__file__).parent
CASES_DIR = EVALS_DIR / "cases"
RESULTS_DIR = EVALS_DIR / "results"


def load_cases(ids: list[str] | None = None) -> list[dict]:
    cases = [json.loads(p.read_text()) for p in sorted(CASES_DIR.glob("E1-*.json"))]
    if ids:
        cases = [c for c in cases if c["id"] in ids]
        missing = set(ids) - {c["id"] for c in cases}
        if missing:
            raise SystemExit(f"없는 사례: {sorted(missing)}")
    return cases


class SnapshotTool:
    """도구 자리에 끼우는 대역. 사건 코인으로 불렸는지 확인하고 저장된 응답을 돌려준다."""

    def __init__(self, name: str, coin_code: str, value):
        self.name = name
        self.coin_code = coin_code
        self.value = value

    def invoke(self, args: dict):
        if args.get("coin_code") != self.coin_code:
            raise RuntimeError(f"{self.name}: 사건 코인({self.coin_code})이 아닌 {args.get('coin_code')} 로 호출됨")
        if self.value is None:
            raise RuntimeError(f"{self.name}: 이 사례에는 스냅샷이 없음 — 라우팅이 바뀌었는지 확인")
        return self.value


def _blocked(*args, **kwargs):
    raise RuntimeError("평가 실행 중 외부 호출 차단")


def _loads(text: str | None) -> dict | None:
    try:
        return json.loads(text) if text else None
    except json.JSONDecodeError:
        return None


def run_once(app, case: dict) -> dict:
    """사례 1건을 1회 실행한다. 노드 실패는 예외 대신 node_errors 에 남는다(노드가 fallback 을 돌려주므로)."""
    state = copy.deepcopy(case["state"])
    coin = state["anomaly"]["coin_code"]
    news = case["snapshots"]["news"]
    market_tool = SnapshotTool("query_market_window", coin, case["snapshots"]["market"])
    news_tool = SnapshotTool("search_news", coin, NewsSearchResult.model_validate(news) if news else None)

    nodes: list[str] = []
    outputs: dict = {}
    started = time.perf_counter()
    with (
        patch("src.agent.market_agent.query_market_window", market_tool),
        patch("src.agent.news_agent.search_news", news_tool),
        patch("src.agent.tools.query_market.psycopg2.connect", _blocked),
        patch("src.agent.tools.search_news.requests.get", _blocked),
        get_usage_metadata_callback() as usage,
    ):
        for chunk in app.stream(state, {"recursion_limit": 10}, stream_mode="updates"):
            for node, update in chunk.items():
                nodes.append(node)
                outputs.update(update or {})
    latency = time.perf_counter() - started

    market = _loads(outputs.get("market_analysis"))
    news_out = _loads(outputs.get("news_analysis"))
    report = _loads(outputs.get("final_report"))
    node_errors = []
    if market is None or market.get("claim", "").startswith("[ERROR]"):
        node_errors.append("market_analyst")
    # "[ERROR] 뉴스 조회 실패"는 스냅샷이 error 인 사례의 정상 경로라 노드 실패로 세지 않는다
    if "news_analyst" in nodes and (news_out is None or "[ERROR] 뉴스 분석 실패" in news_out.get("headlines", [])):
        node_errors.append("news_analyst")
    if report is None or report.get("root_cause", "").startswith("[ERROR]"):
        node_errors.append("report_writer")

    report_ok = "report_writer" not in node_errors
    news_ok = news_out is not None and "news_analyst" not in node_errors
    return {
        "nodes": nodes,
        "action": report["recommended_action"] if report_ok else None,
        "confidence": report["confidence"] if report_ok else None,
        "relevance_score": news_out["relevance_score"] if news_ok else None,
        "sentiment": news_out["sentiment"] if news_ok else None,
        "node_errors": node_errors,
        "latency_s": round(latency, 2),
        "usage": dict(usage.usage_metadata),
        "outputs": {"market_analysis": market, "news_analysis": news_out, "final_report": report},
    }


def _rate(values: list[bool | None]) -> float | None:
    scored = [v for v in values if v is not None]
    return sum(scored) / len(scored) if scored else None


def summarize(records: list[dict], runs: int) -> dict:
    """축별로 실행 회차마다 통과율을 내고, 회차 간 최소·최대·평균을 기록한다."""
    summary: dict = {}
    for axis in AXES:
        per_run = [_rate([r["scores"][axis] for r in records if r["run"] == i]) for i in range(runs)]
        valid = [v for v in per_run if v is not None]
        n_scored = sum(1 for r in records if r["run"] == 0 and r["scores"][axis] is not None)
        summary[axis] = {
            "per_run": per_run,
            "min": min(valid) if valid else None,
            "max": max(valid) if valid else None,
            "mean": mean(valid) if valid else None,
            "n_cases": n_scored,
        }
    hit = [r["confidence"] for r in records if r["scores"]["judgment"] is True and r["confidence"] is not None]
    miss = [r["confidence"] for r in records if r["scores"]["judgment"] is False and r["confidence"] is not None]
    summary["confidence"] = {"judgment_hit_mean": mean(hit) if hit else None, "judgment_miss_mean": mean(miss) if miss else None}
    tokens: dict = {}
    for r in records:
        for model, u in r["usage"].items():
            t = tokens.setdefault(model, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
            for k in t:
                t[k] += u.get(k, 0)
    summary["tokens"] = tokens
    summary["graph_runs"] = len(records)
    summary["node_error_runs"] = sum(1 for r in records if r["node_errors"])
    summary["latency_s_mean"] = round(mean(r["latency_s"] for r in records), 2) if records else None
    return summary


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False).stdout.strip()


def _fmt(rate: float | None) -> str:
    return "-" if rate is None else f"{rate * 100:.0f}%"


def print_report(cases: list[dict], records: list[dict], summary: dict, runs: int) -> None:
    print(f"\n{'case':6} {'label':9} " + " ".join(f"{'run' + str(i + 1):10}" for i in range(runs)) + " news(label/score)")
    for case in cases:
        rs = sorted((r for r in records if r["case_id"] == case["id"]), key=lambda r: r["run"])
        cells = [f"{(r['action'] or 'FAIL')}{'✓' if r['scores']['judgment'] else '✗'}" for r in rs]
        scores = ",".join("-" if r["relevance_score"] is None else f"{r['relevance_score']:.2f}" for r in rs)
        print(f"{case['id']:6} {case['label']['recommended_action']:9} " + " ".join(f"{c:10}" for c in cells)
              + f" {case['label']['news_relevant']}/{scores}")
    print()
    for axis in AXES:
        s = summary[axis]
        print(f"{axis:9} {_fmt(s['min'])}~{_fmt(s['max'])} (평균 {_fmt(s['mean'])}, 채점 사례 {s['n_cases']}건)")
    c = summary["confidence"]
    print(f"confidence 평균 — 맞힘 {c['judgment_hit_mean']} / 틀림 {c['judgment_miss_mean']}")
    print(f"토큰 {summary['tokens']} | 노드 실패 실행 {summary['node_error_runs']}/{summary['graph_runs']} | 평균 {summary['latency_s_mean']}s")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--cases", nargs="*", help="사례 ID (기본: 전체)")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    app = build_analysis_workflow()
    started_at = datetime.now(timezone.utc)
    records = []
    for run in range(args.runs):
        for case in cases:
            result = run_once(app, case)
            scores = score_run(case["label"], case["state"]["anomaly"]["firing_indicators"], result)
            records.append({"case_id": case["id"], "run": run, "scores": scores, **result})
            print(f"run{run + 1} {case['id']}: {result['action']} {scores} {result['latency_s']}s", flush=True)

    summary = summarize(records, args.runs)
    sha = _git("rev-parse", "--short", "HEAD")
    meta = {
        "set_version": cases[0]["set_version"] if cases else None,
        "label_status": sorted({c["label"]["status"] for c in cases}),
        "model": market_agent.LLM_MODEL,
        "commit": sha,
        "src_dirty": bool(_git("status", "--porcelain", "--", "src")),
        "runs": args.runs,
        "cases": [c["id"] for c in cases],
        "started_at": started_at.isoformat(timespec="seconds"),
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{started_at:%Y%m%dT%H%M%SZ}_{sha}.json"
    out.write_text(json.dumps({"meta": meta, "summary": summary, "records": records}, ensure_ascii=False, indent=2) + "\n")
    print_report(cases, records, summary, args.runs)
    print(f"\n저장: {out.relative_to(EVALS_DIR.parent)}")


if __name__ == "__main__":
    main()
