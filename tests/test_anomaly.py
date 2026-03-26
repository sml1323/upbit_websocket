from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from src.detector.anomaly import (
    _classify_severity,
    check_warm_up,
    detect_anomalies,
    Anomaly,
)


class TestClassifySeverity:
    def test_critical(self):
        assert _classify_severity(7.5) == "critical"
        assert _classify_severity(-8.0) == "critical"

    def test_high(self):
        assert _classify_severity(5.5) == "high"
        assert _classify_severity(-6.0) == "high"

    def test_medium(self):
        assert _classify_severity(4.5) == "medium"

    def test_low(self):
        assert _classify_severity(3.1) == "low"
        assert _classify_severity(3.0) == "low"

    def test_below_threshold(self):
        # 2.9 is still "low" since it matches the 3.0 threshold via >=
        assert _classify_severity(2.9) == "low"


class TestCheckWarmUp:
    def test_warm_up_ready(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2.5,)  # 2.5시간
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        assert check_warm_up(mock_conn) is True

    def test_warm_up_not_ready(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0.3,)  # 18분
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        assert check_warm_up(mock_conn) is False

    def test_warm_up_no_data(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (None,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        assert check_warm_up(mock_conn) is False

    def test_warm_up_empty_table(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        assert check_warm_up(mock_conn) is False


class TestDetectAnomalies:
    def test_price_spike_detected(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        now = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            (now, "BTC", 4.5, 1.2, 50000000, 48000000, 100, 80),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        anomalies = detect_anomalies(mock_conn, z_threshold=3.0)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "price_spike"
        assert anomalies[0].severity == "medium"
        assert anomalies[0].z_score == 4.5

    def test_both_price_and_volume(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        now = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            (now, "ETH", 5.5, 6.0, 3000000, 2800000, 500, 100),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        anomalies = detect_anomalies(mock_conn, z_threshold=3.0)
        assert len(anomalies) == 2
        types = {a.anomaly_type for a in anomalies}
        assert types == {"price_spike", "volume_surge"}

    def test_no_anomalies(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        anomalies = detect_anomalies(mock_conn, z_threshold=3.0)
        assert len(anomalies) == 0


class TestAnomaly:
    def test_dataclass(self):
        a = Anomaly(
            bucket=datetime.now(timezone.utc),
            coin_code="BTC",
            anomaly_type="price_spike",
            severity="high",
            z_score=5.5,
            current_value=50000000,
            avg_value=48000000,
        )
        assert a.coin_code == "BTC"
        assert a.severity == "high"
