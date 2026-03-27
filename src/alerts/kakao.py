"""KakaoTalk '나에게 보내기' 알림."""

import json
import os

import requests

from src.config import setup_logging

logger = setup_logging("kakao-alert")

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
_access_token = os.getenv("KAKAO_ACCESS_TOKEN", "")
_refresh_token_value = os.getenv("KAKAO_REFRESH_TOKEN", "")

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3001/d/upbit-market-overview")

SEVERITY_EMOJI = {
    "critical": "\U0001f534",
    "high": "\U0001f7e0",
    "medium": "\U0001f7e1",
    "low": "\U0001f7e2",
}

# severity=low는 skip (일일 전송 제한 대응)
MIN_SEVERITY = {"medium", "high", "critical"}


def _send_memo(access_token: str, text: str) -> bool | None:
    """카카오톡 나에게 보내기 API 호출. 성공 시 True, 401 시 None, 그 외 실패 시 False."""
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}"}
    template = {
        "object_type": "text",
        "text": text[:200],
        "link": {
            "web_url": GRAFANA_URL,
            "mobile_web_url": GRAFANA_URL,
        },
        "button_title": "Grafana 대시보드",
    }
    try:
        resp = requests.post(
            url,
            headers=headers,
            data={"template_object": json.dumps(template)},
            timeout=10,
        )
        if resp.status_code == 401:
            return None  # token expired
        resp.raise_for_status()
        return True
    except requests.exceptions.HTTPError:
        logger.error("Kakao 전송 실패: %s", resp.text)
        return False
    except Exception as e:
        logger.error("Kakao 전송 오류: %s", e)
        return False


def _refresh_access_token() -> str | None:
    """access_token 만료 시 refresh_token으로 갱신."""
    global _refresh_token_value
    if not _refresh_token_value or not KAKAO_REST_API_KEY:
        return None

    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "refresh_token": _refresh_token_value,
    }
    try:
        resp = requests.post(url, data=data, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        new_access = body.get("access_token")
        if "refresh_token" in body:
            _refresh_token_value = body["refresh_token"]
            logger.info("Kakao refresh_token 갱신됨")
        logger.info("Kakao access_token 갱신 성공")
        return new_access
    except Exception as e:
        logger.error("Kakao 토큰 갱신 실패: %s", e)
        return None


def send_kakao_alert(
    coin_code: str,
    anomaly_type: str,
    severity: str,
    z_score: float,
    incident_id: str,
) -> bool:
    """카카오톡으로 이상 감지 알림을 전송합니다."""
    global _access_token

    if not _access_token:
        logger.debug("Kakao 설정 없음. 스킵.")
        return False

    if severity not in MIN_SEVERITY:
        logger.debug("Kakao: severity=%s skip (medium 이상만 전송)", severity)
        return False

    emoji = SEVERITY_EMOJI.get(severity, "\u26a0\ufe0f")
    text = (
        f"{emoji} Market Incident\n\n"
        f"{coin_code} | {severity.upper()}\n"
        f"{anomaly_type}\n"
        f"Score: {z_score:.2f}"
    )

    result = _send_memo(_access_token, text)
    if result is True:
        logger.info("Kakao 알림 전송: %s %s", coin_code, severity)
        return True

    if result is None:
        # 401 → 토큰 갱신 후 1회 재시도
        new_token = _refresh_access_token()
        if new_token:
            _access_token = new_token
            retry = _send_memo(_access_token, text)
            if retry is True:
                logger.info("Kakao 알림 전송 (토큰 갱신 후): %s %s", coin_code, severity)
                return True

    logger.warning("Kakao 알림 실패: %s %s", coin_code, severity)
    return False
