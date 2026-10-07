"""E1 평가 사례 생성기 — 과거 시세에 실제 감지기를 다시 돌려 사건·도구 응답 스냅샷을 만든다.

DB 의 incidents 가 비어 있어(2026-10-07 확인) 저장된 사건 대신 agg_1min 에서 사건을 재구성한다.
- 사건: 기준 시각(asof)까지 1440분 창을 잘라 EnsembleScorer.score() — 스케줄러와 같은 감지기·가중치
- 초기 상태: graph.build_initial_state() — 운영 경로와 같은 함수
- 시장 스냅샷: asof 까지 60분 행을 summarize_market_rows() 로 요약 — query_market_window 와 같은 형식
- 뉴스 스냅샷: 운영 search_news 를 그대로 부르되 SerpAPI 요청에만 날짜 범위(asof 전날~당일, KST)를 붙인다

실행(DB 는 읽기만, SerpAPI 는 사례당 1회 호출):
    DB_HOST=localhost uv run python -m evals.build_cases            # 없는 사례만 생성
    DB_HOST=localhost uv run python -m evals.build_cases --rebuild  # 스냅샷 다시 생성(label 은 유지)
"""

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import psycopg2

from src.agent.graph import NEWS_REQUIRED_INDICATORS, build_initial_state
from src.agent.tools import search_news as search_news_module
from src.agent.tools.query_market import summarize_market_rows
from src.agent.tools.search_news import SERPAPI_URL, search_news
from src.config import get_db_dsn
from src.scheduler import _scorer

SET_VERSION = "e1-v1"
CASES_DIR = Path(__file__).parent / "cases"
KST = timezone(timedelta(hours=9))

# 2026-09-28~10-07 백필 스캔 5,173건에서 고른 10건. 고른 기준·정답 기준은 evals/README.md
CASE_SPECS = [
    {"id": "E1-01", "coin": "TRAC", "asof": "2026-10-01T01:39:00+00:00", "difficulty": "L1", "note": "유동성 충분, 60분 +17% 급등"},
    {"id": "E1-02", "coin": "SOON", "asof": "2026-09-30T01:58:00+00:00", "difficulty": "L1", "note": "유동성 충분, 60분 -9% 급락"},
    {"id": "E1-03", "coin": "BTC", "asof": "2026-09-29T14:06:00+00:00", "difficulty": "L1", "note": "대형 코인, 변동 -0.4% 인데 지표 2개 발동"},
    {"id": "E1-04", "coin": "ETH", "asof": "2026-10-02T08:19:00+00:00", "difficulty": "L2", "note": "대형 코인, 변동 +1.0% 경계값"},
    {"id": "E1-05", "coin": "DOGE", "asof": "2026-10-02T04:55:00+00:00", "difficulty": "L2", "note": "대형 코인, 변동 +2.3%"},
    {"id": "E1-06", "coin": "ICX", "asof": "2026-10-01T08:59:00+00:00", "difficulty": "L2", "note": "변동 -6.6%·고저폭 17% 인데 지표 2개뿐(규칙상 ALERT)"},
    {"id": "E1-07", "coin": "SIGN", "asof": "2026-09-29T02:24:00+00:00", "difficulty": "L2", "note": "지표 4개 전부, 변동 -6.6%"},
    {"id": "E1-08", "coin": "XRP", "asof": "2026-10-02T19:22:00+00:00", "difficulty": "L3", "note": "수집 공백 직후 지표 4개 전부, 60분 거래 5건"},
    {"id": "E1-09", "coin": "SENT", "asof": "2026-10-03T13:23:00+00:00", "difficulty": "L3", "note": "VWAP 하나만 발동(뉴스 노드 생략), 60분 거래 7건"},
    {"id": "E1-10", "coin": "LIT", "asof": "2026-10-03T17:34:00+00:00", "difficulty": "L3", "note": "지표 4개 전부, 변동 +3.9%(규칙상 ESCALATE)"},
]

OHLCV_COLUMNS = ["bucket", "code", "open", "high", "low", "close", "volume", "trade_count"]


def _detect(conn, coin: str, asof: datetime):
    """asof 시점에 스케줄러가 봤을 1440분 창으로 감지기를 돌린다."""
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT {", ".join(OHLCV_COLUMNS)} FROM agg_1min
                WHERE code = %s AND bucket > %s - interval '1440 minutes' AND bucket <= %s
                ORDER BY bucket""",
            (coin, asof, asof),
        )
        window = pd.DataFrame(cur.fetchall(), columns=OHLCV_COLUMNS)
    return _scorer.score(coin, window)


def _market_snapshot(conn, coin: str, asof: datetime, minutes: int = 60) -> tuple[str, int]:
    """query_market_window 가 asof 에 돌려줬을 문자열. now() 대신 asof 를 쓴다."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT bucket, open, high, low, close, volume, trade_count FROM agg_1min
               WHERE code = %s AND bucket > %s - make_interval(mins => %s) AND bucket <= %s
               ORDER BY bucket DESC LIMIT 60""",
            (coin, asof, minutes, asof),
        )
        rows = cur.fetchall()
    return summarize_market_rows(coin, minutes, rows), len(rows)


def _btc_rows_60m(conn, asof: datetime) -> int:
    """수집 상태 지표: BTC 는 매분 체결되므로 60 미만이면 파이프라인 공백."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM agg_1min WHERE code = 'BTC' AND bucket > %s - interval '60 minutes' AND bucket <= %s",
            (asof, asof),
        )
        return cur.fetchone()[0]


def _news_snapshot(coin: str, asof: datetime) -> tuple[dict, list[dict]]:
    """운영 search_news 를 그대로 실행하고 SerpAPI 요청에만 날짜 범위를 붙인다.

    반환: (주입할 NewsSearchResult JSON, 라벨 참고용 기사 날짜 목록 — 주입하지 않음)
    """
    day = asof.astimezone(KST)
    tbs = f"cdr:1,cd_min:{(day - timedelta(days=1)):%m/%d/%Y},cd_max:{day:%m/%d/%Y}"
    raw_dates: list[dict] = []
    original_get_json = search_news_module._get_json

    def get_json_with_date_range(url: str, params: dict) -> object:
        if url != SERPAPI_URL:
            return original_get_json(url, params)
        payload = original_get_json(url, {**params, "tbs": tbs})
        if isinstance(payload, dict):
            for item in payload.get("news_results", []) or []:
                if isinstance(item, dict):
                    raw_dates.append({"title": item.get("title"), "date": item.get("date")})
        return payload

    with patch.object(search_news_module, "_get_json", get_json_with_date_range):
        result = search_news.invoke({"coin_code": coin})
    return result.model_dump(mode="json"), raw_dates


def build_case(conn, spec: dict) -> dict:
    asof = datetime.fromisoformat(spec["asof"])
    detected = _detect(conn, spec["coin"], asof)
    if not detected.is_anomaly:
        raise RuntimeError(f"{spec['id']}: asof 시점에 감지기가 이상치로 판정하지 않음")

    state = build_initial_state(detected, incident_id=spec["id"])
    market, market_rows = _market_snapshot(conn, spec["coin"], asof)
    firing = state["anomaly"]["firing_indicators"]
    routes_news = bool(set(firing) & NEWS_REQUIRED_INDICATORS)
    news, news_dates = _news_snapshot(spec["coin"], asof) if routes_news else (None, [])

    return {
        "id": spec["id"],
        "set_version": SET_VERSION,
        "difficulty": spec["difficulty"],
        "note": spec["note"],
        "source": {
            "method": "backfill-detector",
            "coin_code": spec["coin"],
            "asof": asof.isoformat(),
            "pipeline_btc_rows_60m": _btc_rows_60m(conn, asof),
            "market_rows_60m": market_rows,
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "state": state,
        # 뉴스 노드가 실행되지 않는 사례는 news 가 null — 실행되면 스냅샷 누락으로 실패해야 한다
        "snapshots": {"market": market, "news": news},
        "reference": {"news_dates": news_dates},
        "label": {
            "expected_nodes": ["market_analyst", "news_analyst", "report_writer"] if routes_news
            else ["market_analyst", "report_writer"],
            "recommended_action": None,
            "news_relevant": None,
            "rationale": "",
            "status": "todo",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="스냅샷을 다시 만든다. label 은 유지")
    args = parser.parse_args()

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    conn = psycopg2.connect(get_db_dsn())
    try:
        for spec in CASE_SPECS:
            path = CASES_DIR / f"{spec['id']}.json"
            if path.exists() and not args.rebuild:
                print(f"{spec['id']}: 있음 — 건너뜀")
                continue
            case = build_case(conn, spec)
            if path.exists():
                case["label"] = json.loads(path.read_text())["label"]
            path.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n")
            news = case["snapshots"]["news"]
            print(
                f"{spec['id']} {spec['coin']}: firing={case['state']['anomaly']['firing_indicators']} "
                f"news={news['status'] if news else '-'}({len(news['articles']) if news else 0})"
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
