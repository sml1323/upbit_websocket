import os

import psycopg2
from apscheduler.schedulers.blocking import BlockingScheduler

from src.config import get_db_dsn, setup_logging
from src.detector.anomaly import check_warm_up
from src.detector.base import IndicatorRegistry
from src.detector.zscore import ZScoreIndicator
from src.detector.bollinger import BollingerBandsIndicator
from src.detector.rsi import RSIIndicator
from src.detector.vwap import VWAPIndicator
from src.detector.ensemble import (
    EnsembleScorer,
    prefilter_coins,
    save_incident,
    save_snapshots,
)
from src.agent.graph import analyze_anomaly
from src.alerts.telegram import send_alert
from src.alerts.kakao import send_kakao_alert

logger = setup_logging("scheduler")

DETECTION_INTERVAL_MIN = 5
PREFILTER_Z_THRESHOLD = 2.0
# 한 사이클에 LLM 분석·알림까지 가는 최대 건수. 나머지는 감지만 저장(status='skipped').
# 상한이 없으면 이상 징후 수십 건이 5분마다 OpenAI·SerpAPI(월 100회)를 호출한다.
MAX_ANALYSES_PER_CYCLE = int(os.getenv("MAX_ANALYSES_PER_CYCLE", "3"))


def _build_registry() -> IndicatorRegistry:
    """Register all indicators with their weights."""
    registry = IndicatorRegistry()
    registry.register(ZScoreIndicator(weight=0.30))
    registry.register(BollingerBandsIndicator(weight=0.25))
    registry.register(RSIIndicator(weight=0.20))
    registry.register(VWAPIndicator(weight=0.25))
    return registry


def pick_for_analysis(anomalies: list, limit: int) -> tuple[list, list]:
    """앙상블 점수 → 발화 지표 수가 높은 순으로 limit 건만 분석 대상으로 고른다."""
    ranked = sorted(anomalies, key=lambda r: (r.ensemble_score, r.firing_count), reverse=True)
    return ranked[:limit], ranked[limit:]


def _mark_skipped(conn, incident_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE incidents SET status = 'skipped' WHERE incident_id = %s::uuid",
            (incident_id,),
        )
    conn.commit()


# Build once at module load
_registry = _build_registry()
_scorer = EnsembleScorer(_registry)


def run_cycle():
    """5분마다 실행되는 감지 + Agent 분석 사이클"""
    logger.info("감지 사이클 시작")
    conn = psycopg2.connect(get_db_dsn())

    try:
        if not check_warm_up(conn):
            logger.info("Warm-up 미완료. 스킵.")
            return

        # Step 1: pre-filter — z >= 2.0인 코인만
        coin_codes = prefilter_coins(conn, z_threshold=PREFILTER_Z_THRESHOLD)
        if not coin_codes:
            logger.debug("이상 징후 없음 (pre-filter)")
            return

        logger.info("Pre-filter: %d개 코인 감지", len(coin_codes))

        # Step 2: ensemble scoring
        results = _scorer.score_batch(coin_codes, conn)
        logger.info("Ensemble 스코어링 완료: %d개 코인", len(results))

        # Step 3: save snapshots for Grafana (all results)
        save_snapshots(conn, results)

        # Step 4: process anomalies
        anomalies = [r for r in results if r.is_anomaly]
        if not anomalies:
            logger.info("Ensemble 판정: 이상 없음 — 사이클 완료")
            return

        to_analyze, skipped = pick_for_analysis(anomalies, MAX_ANALYSES_PER_CYCLE)
        logger.info(
            "%d건 이상 징후 감지 (ensemble) — 상위 %d건 분석, %d건 감지만 저장",
            len(anomalies), len(to_analyze), len(skipped),
        )
        for result in skipped:
            _mark_skipped(conn, save_incident(conn, result))

        for result in to_analyze:
            incident_id = save_incident(conn, result)
            analyze_anomaly(result, incident_id)

            firing = [s.indicator_name for s in result.signals if s.is_anomaly]
            alert_type = f"ensemble({','.join(firing)})"

            try:
                send_alert(
                    result.coin_code, alert_type,
                    result.severity, result.ensemble_score, incident_id,
                )
            except Exception:
                logger.exception("Telegram 알림 실패")

            try:
                send_kakao_alert(
                    result.coin_code, alert_type,
                    result.severity, result.ensemble_score, incident_id,
                )
            except Exception:
                logger.exception("KakaoTalk 알림 실패")

    except Exception:
        logger.exception("감지 사이클 오류")
    finally:
        conn.close()


def main():
    indicators = [ind.name for ind in _registry.get_all()]
    logger.info(
        "스케줄러 시작 — %d분 간격, indicators=%s",
        DETECTION_INTERVAL_MIN, indicators,
    )

    # 시작 시 즉시 1회 실행
    run_cycle()

    scheduler = BlockingScheduler()
    scheduler.add_job(run_cycle, "interval", minutes=DETECTION_INTERVAL_MIN)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")


if __name__ == "__main__":
    main()
