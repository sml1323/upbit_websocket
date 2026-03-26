from datetime import datetime, timezone

import psycopg2
from langchain_core.tools import tool

from src.config import get_db_dsn, setup_logging

logger = setup_logging("tool-query-market")


@tool
def query_market_window(coin_code: str, minutes: int = 60) -> str:
    """TimescaleDB에서 특정 코인의 최근 N분 시장 데이터를 조회합니다.

    Args:
        coin_code: 코인 코드 (예: BTC, ETH)
        minutes: 조회할 시간 범위 (분, 기본 60분)

    Returns:
        시장 데이터 요약 문자열
    """
    query = """
        SELECT
            bucket, open, high, low, close, volume, trade_count
        FROM agg_1min
        WHERE code = %s
          AND bucket >= now() - make_interval(mins => %s)
        ORDER BY bucket DESC
        LIMIT 60
    """
    conn = None
    try:
        conn = psycopg2.connect(get_db_dsn())
        with conn.cursor() as cur:
            cur.execute(query, (coin_code, minutes))
            rows = cur.fetchall()

        if not rows:
            return f"{coin_code}: 최근 {minutes}분간 데이터 없음"

        latest = rows[0]
        oldest = rows[-1]
        high = max(r[2] for r in rows)
        low = min(r[3] for r in rows)
        total_volume = sum(r[5] for r in rows)
        total_trades = sum(r[6] for r in rows)

        price_change = ((latest[4] - oldest[1]) / oldest[1]) * 100 if oldest[1] else 0

        return (
            f"[{coin_code}] 최근 {minutes}분 요약\n"
            f"- 현재가: {latest[4]:,.0f} / 시가: {oldest[1]:,.0f}\n"
            f"- 변동률: {price_change:+.2f}%\n"
            f"- 고가: {high:,.0f} / 저가: {low:,.0f}\n"
            f"- 총 거래량: {total_volume:,.4f}\n"
            f"- 총 거래 수: {total_trades:,}\n"
            f"- 데이터 포인트: {len(rows)}개 (1분 단위)"
        )
    except Exception as e:
        logger.error("시장 데이터 조회 실패: %s", e)
        return f"시장 데이터 조회 실패: {e}"
    finally:
        if conn:
            conn.close()
