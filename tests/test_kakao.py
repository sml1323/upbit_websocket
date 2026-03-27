"""Tests for KakaoTalk alert module."""

from unittest.mock import patch, MagicMock

from src.alerts.kakao import send_kakao_alert, _send_memo, _refresh_access_token


class TestSendMemo:
    @patch("src.alerts.kakao.requests.post")
    def test_success(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()
        result = _send_memo("token123", "test message")
        assert result is True

    @patch("src.alerts.kakao.requests.post")
    def test_401_returns_none(self, mock_post):
        mock_post.return_value = MagicMock(status_code=401)
        result = _send_memo("expired_token", "test")
        assert result is None

    @patch("src.alerts.kakao.requests.post")
    def test_error_returns_false(self, mock_post):
        mock_post.side_effect = Exception("network error")
        result = _send_memo("token", "test")
        assert result is False


class TestRefreshAccessToken:
    @patch("src.alerts.kakao.requests.post")
    @patch("src.alerts.kakao.KAKAO_REST_API_KEY", "test_key")
    @patch("src.alerts.kakao._refresh_token_value", "refresh_123")
    def test_success(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.ok = True
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
        }
        result = _refresh_access_token()
        assert result == "new_access"

    @patch("src.alerts.kakao.requests.post")
    @patch("src.alerts.kakao.KAKAO_REST_API_KEY", "test_key")
    @patch("src.alerts.kakao._refresh_token_value", "")
    def test_no_refresh_token(self, mock_post):
        result = _refresh_access_token()
        assert result is None
        mock_post.assert_not_called()

    @patch("src.alerts.kakao.requests.post")
    @patch("src.alerts.kakao.KAKAO_REST_API_KEY", "test_key")
    @patch("src.alerts.kakao._refresh_token_value", "refresh_123")
    def test_failure(self, mock_post):
        mock_post.side_effect = Exception("auth error")
        result = _refresh_access_token()
        assert result is None


class TestSendKakaoAlert:
    @patch("src.alerts.kakao._send_memo", return_value=True)
    @patch("src.alerts.kakao._access_token", "token123")
    def test_success(self, mock_send):
        result = send_kakao_alert("BTC", "ensemble", "critical", 0.85, "inc-1")
        assert result is True
        mock_send.assert_called_once()

    @patch("src.alerts.kakao._access_token", "")
    def test_no_token_skips(self):
        result = send_kakao_alert("BTC", "ensemble", "critical", 0.85, "inc-1")
        assert result is False

    @patch("src.alerts.kakao._send_memo", return_value=True)
    @patch("src.alerts.kakao._access_token", "token123")
    def test_low_severity_skips(self, mock_send):
        result = send_kakao_alert("BTC", "ensemble", "low", 0.3, "inc-1")
        assert result is False
        mock_send.assert_not_called()

    @patch("src.alerts.kakao._refresh_access_token", return_value="new_token")
    @patch("src.alerts.kakao._send_memo")
    @patch("src.alerts.kakao._access_token", "old_token")
    def test_401_retry_success(self, mock_send, mock_refresh):
        # First call returns None (401), second returns True
        mock_send.side_effect = [None, True]
        result = send_kakao_alert("BTC", "ensemble", "high", 0.7, "inc-1")
        assert result is True
        assert mock_send.call_count == 2
        mock_refresh.assert_called_once()

    @patch("src.alerts.kakao._refresh_access_token", return_value=None)
    @patch("src.alerts.kakao._send_memo", return_value=None)
    @patch("src.alerts.kakao._access_token", "old_token")
    def test_401_refresh_fails(self, mock_send, mock_refresh):
        result = send_kakao_alert("BTC", "ensemble", "medium", 0.5, "inc-1")
        assert result is False
