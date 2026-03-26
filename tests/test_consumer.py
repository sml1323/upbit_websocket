from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from src.pipeline.consumer import parse_ticker_message, insert_batch


class TestParseTickerMessage:
    def test_normal_message(self):
        data = {
            "trade_timestamp": "1700000000000",
            "code": "KRW-BTC",
            "trade_price": 50000000,
            "trade_volume": 0.5,
        }
        result = parse_ticker_message(data)
        assert result is not None
        time_val, code, price, volume = result
        assert code == "BTC"
        assert price == 50000000
        assert volume == 0.5
        assert isinstance(time_val, datetime)
        assert time_val.tzinfo == timezone.utc

    def test_missing_timestamp_uses_now(self):
        data = {
            "code": "KRW-ETH",
            "trade_price": 3000000,
            "trade_volume": 1.0,
        }
        result = parse_ticker_message(data)
        assert result is not None
        time_val, code, price, volume = result
        assert code == "ETH"
        # time should be close to now
        assert (datetime.now(timezone.utc) - time_val).total_seconds() < 5

    def test_missing_price_returns_none(self):
        data = {
            "trade_timestamp": "1700000000000",
            "code": "KRW-BTC",
            "trade_volume": 0.5,
        }
        assert parse_ticker_message(data) is None

    def test_missing_volume_returns_none(self):
        data = {
            "trade_timestamp": "1700000000000",
            "code": "KRW-BTC",
            "trade_price": 50000000,
        }
        assert parse_ticker_message(data) is None


class TestInsertBatch:
    def test_empty_batch_does_nothing(self):
        mock_conn = MagicMock()
        insert_batch(mock_conn, [])
        mock_conn.cursor.assert_not_called()

    @patch("src.pipeline.consumer.execute_values")
    def test_successful_batch_commits(self, mock_exec_values):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        batch = [
            (datetime.now(timezone.utc), "BTC", 50000000, 0.5),
            (datetime.now(timezone.utc), "ETH", 3000000, 1.0),
        ]
        insert_batch(mock_conn, batch)
        mock_exec_values.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_conn.rollback.assert_not_called()

    def test_failed_batch_rolls_back(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.commit.side_effect = Exception("DB error")

        batch = [
            (datetime.now(timezone.utc), "BTC", 50000000, 0.5),
        ]
        try:
            insert_batch(mock_conn, batch)
            assert False, "Should have raised"
        except Exception:
            mock_conn.rollback.assert_called_once()
