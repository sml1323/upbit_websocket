import psycopg2
from apscheduler.schedulers.blocking import BlockingScheduler

from src.config import get_db_dsn, setup_logging
from src.detector.anomaly import check_warm_up, detect_anomalies, save_incident
from src.agent.graph import analyze_anomaly

logger = setup_logging("scheduler")

DETECTION_INTERVAL_MIN = 5
Z_THRESHOLD = 3.0


def run_cycle():
    """5분마다 실행되는 감지 + Agent 분석 사이클"""
    logger.info("감지 사이클 시작")
    conn = psycopg2.connect(get_db_dsn())

    try:
        if not check_warm_up(conn):
            logger.info("Warm-up 미완료. 스킵.")
            return

        anomalies = detect_anomalies(conn, z_threshold=Z_THRESHOLD)
        if not anomalies:
            logger.debug("이상 징후 없음")
            return

        logger.info("%d건 이상 징후 감지", len(anomalies))
        for anomaly in anomalies:
            incident_id = save_incident(conn, anomaly)
            analyze_anomaly(anomaly, incident_id)

    except Exception:
        logger.exception("감지 사이클 오류")
    finally:
        conn.close()


def main():
    logger.info(
        "스케줄러 시작 — %d분 간격, z-threshold=%.1f",
        DETECTION_INTERVAL_MIN, Z_THRESHOLD,
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
