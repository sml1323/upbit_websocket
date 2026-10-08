"""리포트 뷰어 데모용 인시던트를 incidents 테이블에 넣는다 (source='demo').

E1 평가셋(evals/cases)의 감지 상태 + 최신 평가 실행(evals/results, run 0)의 실제 노드 출력을 쓴다.
감지 시각은 사례의 asof 그대로라서 agg_1min 에 그 시간대 캔들이 있으면 차트도 그려진다.
실제 파이프라인(graph._save_agent_report)이 저장하는 것만 넣는다 — 검색 도구의 원본 기사(news_context)는 넣지 않는다.

    uv run python scripts/seed_demo_incidents.py           # 10건 넣기 (다시 돌려도 덮어쓰기)
    uv run python scripts/seed_demo_incidents.py --drip    # 사례 1건을 지웠다 다시 넣어 감지 → 분석 완료 흐름 재현 (실시간 데모)
    uv run python scripts/seed_demo_incidents.py --clear   # demo 행 지우기

로컬에서 돌릴 때는 DB_HOST=localhost 를 앞에 붙인다 (.env 는 컨테이너 기준 timescaledb).
"""

import argparse
import json
import random
import re
import sys
import time
import uuid
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import get_db_dsn  # noqa: E402

CASES_DIR = ROOT / "evals" / "cases"
RESULTS_DIR = ROOT / "evals" / "results"
DEMO_NAMESPACE = uuid.UUID("6f1c2a4e-3b7d-4c55-9a51-0d6e0c2b9f10")

# "  - zscore: 5.47 [⚠️ 이상] (price_zscore=3.89, volume_zscore=5.47, ...)"
_LINE = re.compile(r"-\s*(\w+):\s*[-\d.]+\s*\[[^\]]*\]\s*\((.*)\)")


def _coerce(value: str):
    try:
        return float(value)
    except ValueError:
        return value


def parse_indicator_details(text: str) -> dict:
    details = {}
    for m in _LINE.finditer(text or ""):
        pairs = (kv.split("=", 1) for kv in m.group(2).split(", ") if "=" in kv)
        details[m.group(1)] = {k.strip(): _coerce(v.strip()) for k, v in pairs}
    return details


def load_demo_rows() -> list[dict]:
    result_file = sorted(RESULTS_DIR.glob("*.json"))[-1]
    records = {
        r["case_id"]: r
        for r in json.loads(result_file.read_text())["records"]
        if r["run"] == 0
    }
    rows = []
    for path in sorted(CASES_DIR.glob("*.json")):
        case = json.loads(path.read_text())
        anomaly = case["state"]["anomaly"]
        outputs = (records.get(case["id"]) or {}).get("outputs") or {}
        report = outputs.get("final_report")
        details = parse_indicator_details(case["state"]["indicator_details"])
        rows.append({
            "incident_id": str(uuid.uuid5(DEMO_NAMESPACE, case["id"])),
            "detected_at": case["source"]["asof"],
            "coin_code": anomaly["coin_code"],
            "severity": anomaly["severity"],
            "z_score": (details.get("zscore") or {}).get("price_zscore"),
            "ensemble_score": anomaly["ensemble_score"],
            "firing_indicators": anomaly["firing_indicators"],
            "indicator_details": json.dumps(details),
            # graph._save_agent_report 와 같은 모양: 노드 출력은 JSON 문자열
            "agent_report": json.dumps({
                key: json.dumps(outputs[key], ensure_ascii=False) if outputs.get(key) else ""
                for key in ("market_analysis", "news_analysis", "final_report")
            }, ensure_ascii=False) if report else None,
            "news_context": None,
            "confidence_score": report.get("confidence") if report else None,
            "status": "analyzed" if report else "open",
        })
    return rows


UPSERT = """
INSERT INTO incidents (incident_id, detected_at, coin_code, anomaly_type, severity, z_score,
                       agent_report, news_context, confidence_score, source, status,
                       ensemble_score, firing_indicators, indicator_details)
VALUES (%(incident_id)s, %(detected_at)s, %(coin_code)s, 'ensemble', %(severity)s, %(z_score)s,
        %(agent_report)s, %(news_context)s, %(confidence_score)s, 'demo', %(status)s,
        %(ensemble_score)s, %(firing_indicators)s, %(indicator_details)s)
ON CONFLICT (incident_id) DO UPDATE SET
    detected_at = EXCLUDED.detected_at, severity = EXCLUDED.severity, z_score = EXCLUDED.z_score,
    agent_report = EXCLUDED.agent_report, news_context = EXCLUDED.news_context,
    confidence_score = EXCLUDED.confidence_score, status = EXCLUDED.status,
    ensemble_score = EXCLUDED.ensemble_score, firing_indicators = EXCLUDED.firing_indicators,
    indicator_details = EXCLUDED.indicator_details
"""


def seed(conn) -> None:
    rows = load_demo_rows()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(UPSERT, row)
        # 평가셋에 없는 demo 행(예전 버전 스크립트가 만든 것)은 지운다
        cur.execute(
            "DELETE FROM incidents WHERE source = 'demo' AND NOT (incident_id = ANY(%s::uuid[]))",
            ([r["incident_id"] for r in rows],),
        )
        stale = cur.rowcount
    conn.commit()
    print(f"demo 인시던트 {len(rows)}건 넣음" + (f", 평가셋에 없는 demo {stale}건 지움" if stale else ""))


def drip(conn, delay: float) -> None:
    """사례 1건을 지웠다가 원래 시각·원래 분석 그대로 '분석 중'으로 다시 넣고, delay 초 뒤 분석을 채운다.

    지어낸 데이터 없이 화면의 새 인시던트 알림 → 분석 완료 흐름을 보여주기 위한 것.
    뷰어가 5초마다 폴링하므로 지운 상태를 한 번은 보도록 잠깐 기다렸다 다시 넣는다.
    """
    row = random.choice(load_demo_rows())
    with conn.cursor() as cur:
        cur.execute("DELETE FROM incidents WHERE incident_id = %s::uuid", (row["incident_id"],))
    conn.commit()
    time.sleep(6)

    with conn.cursor() as cur:
        cur.execute(UPSERT, {**row, "agent_report": None, "confidence_score": None, "status": "open"})
    conn.commit()
    print(f"{row['coin_code']} 감지 → {delay:.0f}초 뒤 분석 완료 처리")

    time.sleep(delay)
    with conn.cursor() as cur:
        cur.execute(UPSERT, row)
    conn.commit()
    print(f"{row['coin_code']} 분석 완료")


def clear(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM incidents WHERE source = 'demo'")
        n = cur.rowcount
    conn.commit()
    print(f"demo 인시던트 {n}건 지움")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--drip", action="store_true", help="사례 1건을 지웠다 다시 넣기 (실시간 데모)")
    group.add_argument("--clear", action="store_true", help="demo 행 삭제")
    parser.add_argument("--delay", type=float, default=8.0, help="--drip 에서 분석 완료까지 초")
    args = parser.parse_args()

    conn = psycopg2.connect(get_db_dsn())
    try:
        if args.clear:
            clear(conn)
        elif args.drip:
            drip(conn, args.delay)
        else:
            seed(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
