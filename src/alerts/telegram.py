import os

import requests

from src.config import setup_logging

logger = setup_logging("telegram-alert")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

SEVERITY_EMOJI = {
    "critical": "\U0001f534",  # red circle
    "high": "\U0001f7e0",      # orange circle
    "medium": "\U0001f7e1",    # yellow circle
    "low": "\U0001f7e2",       # green circle
}


def send_alert(
    coin_code: str,
    anomaly_type: str,
    severity: str,
    z_score: float,
    incident_id: str,
) -> bool:
    """Telegram으로 이상 감지 알림을 전송합니다."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.debug("Telegram 설정 없음. 알림 스킵.")
        return False

    emoji = SEVERITY_EMOJI.get(severity, "\u26a0\ufe0f")
    type_kr = "가격 급변" if anomaly_type == "price_spike" else "거래량 급증"

    message = (
        f"{emoji} *Market Incident Copilot*\n\n"
        f"**코인:** {coin_code}\n"
        f"**유형:** {type_kr}\n"
        f"**심각도:** {severity.upper()}\n"
        f"**Z-Score:** {z_score:.2f}\n"
        f"**Incident ID:** `{incident_id}`"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Telegram 알림 전송: %s %s", coin_code, severity)
        return True
    except Exception as e:
        logger.error("Telegram 알림 실패: %s", e)
        return False
