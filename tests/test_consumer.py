from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import psycopg2

from src.pipeline.consumer import (
    parse_ticker_message,
    insert_batch,
    consume_messages,
    DbWriter,
)


class TestParseTickerMessage:
    def test_normal_message(self):
        data = {
            "trade_timestamp": "1700000000000",
            "code": "KRW-BTC",
            "trade_price": 50000000,
            "trade_volume": 0.5,
            "acc_trade_volume": 1234.5,
        }
        result = parse_ticker_message(data)
        assert result is not None
        time_val, code, price, volume, acc_volume = result
        assert code == "BTC"
        assert price == 50000000
        assert volume == 0.5
        assert acc_volume == 1234.5
        assert isinstance(time_val, datetime)
        assert time_val.tzinfo == timezone.utc

    def test_missing_timestamp_uses_now(self):
        data = {
            "code": "KRW-ETH",
            "trade_price": 3000000,
            "trade_volume": 1.0,
            "acc_trade_volume": 10.0,
        }
        result = parse_ticker_message(data)
        assert result is not None
        time_val, code, price, volume, _ = result
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
            "acc_trade_volume": 10.0,
        }
        assert parse_ticker_message(data) is None

    def test_missing_acc_trade_volume_returns_none(self):
        """acc_trade_volume 은 자연키의 일부라 없으면 중복 판정을 못 한다. 버린다."""
        data = {
            "trade_timestamp": "1700000000000",
            "code": "KRW-BTC",
            "trade_price": 50000000,
            "trade_volume": 0.5,
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
        mock_cursor.rowcount = 2

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


def _conn_with_cursor(rowcount: int):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = rowcount
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn


class TestInsertBatchDedupe:
    """at-least-once 재처리로 같은 (time, code) 가 다시 와도 DB 에 중복이 쌓이지 않아야 한다."""

    @patch("src.pipeline.consumer.execute_values")
    def test_query_skips_duplicates_on_natural_key(self, mock_exec_values):
        conn = _conn_with_cursor(rowcount=1)
        insert_batch(conn, [(datetime.now(timezone.utc), "BTC", 1.0, 1.0)])

        query = " ".join(mock_exec_values.call_args.args[1].split())
        assert "INSERT INTO tickers (time, code, trade_price, trade_volume, acc_trade_volume)" in query
        assert "ON CONFLICT (time, code, acc_trade_volume) DO NOTHING" in query

    @patch("src.pipeline.consumer.execute_values")
    def test_returns_inserted_and_skipped_counts(self, mock_exec_values):
        conn = _conn_with_cursor(rowcount=1)
        batch = [
            (datetime.now(timezone.utc), "BTC", 1.0, 1.0),
            (datetime.now(timezone.utc), "ETH", 1.0, 1.0),
            (datetime.now(timezone.utc), "XRP", 1.0, 1.0),
        ]
        assert insert_batch(conn, batch) == (1, 2)

    @patch("src.pipeline.consumer.execute_values")
    def test_logs_skipped_duplicate_count(self, mock_exec_values, caplog):
        conn = _conn_with_cursor(rowcount=1)
        batch = [
            (datetime.now(timezone.utc), "BTC", 1.0, 1.0),
            (datetime.now(timezone.utc), "ETH", 1.0, 1.0),
        ]
        with caplog.at_level("INFO", logger="consumer"):
            insert_batch(conn, batch)
        assert "중복 스킵 1건" in caplog.text

    @patch("src.pipeline.consumer.execute_values")
    def test_sends_whole_batch_in_one_statement(self, mock_exec_values):
        """execute_values 는 page_size 단위로 쿼리를 쪼개고 rowcount 는 마지막 조각만 남는다.
        배치 전체를 한 문장으로 보내야 rowcount 가 실제 삽입 건수가 된다."""
        conn = _conn_with_cursor(rowcount=150)
        batch = [(datetime.now(timezone.utc), f"C{i}", 1.0, 1.0) for i in range(150)]
        insert_batch(conn, batch)
        assert mock_exec_values.call_args.kwargs.get("page_size") == 150


class TestConsumeLoopDedupeCounter:
    @patch("src.pipeline.consumer.insert_batch", return_value=(0, 1))
    @patch("src.pipeline.consumer.create_db_connection")
    @patch("src.pipeline.consumer.create_kafka_consumer")
    def test_logs_cumulative_skipped_count(
        self, mock_create_consumer, mock_create_db, mock_insert, caplog
    ):
        msg = MagicMock()
        msg.error.return_value = None
        msg.value.return_value = (
            b'{"trade_timestamp": "1700000000000", "code": "KRW-BTC",'
            b' "trade_price": 1, "trade_volume": 1, "acc_trade_volume": 1}'
        )
        consumer = MagicMock()
        # 메시지 1건 → 배치 플러시 유도용 None 여러 번 → 종료
        consumer.poll.side_effect = [msg, None, None, KeyboardInterrupt()]
        mock_create_consumer.return_value = consumer

        with patch("src.pipeline.consumer.BATCH_SIZE", 1), caplog.at_level(
            "INFO", logger="consumer"
        ):
            consume_messages()

        assert "누적 중복 스킵 1건" in caplog.text


class TestDbWriterRetry:
    """DB 가 잠깐 끊겨도 컨슈머 프로세스는 살아서 같은 배치를 다시 쓴다.
    배치는 메모리에, offset 은 미커밋 상태라 재시도가 안전하다."""

    def _batch(self, n=2):
        return [(datetime.now(timezone.utc), f"C{i}", 1.0, 1.0) for i in range(n)]

    @patch("src.pipeline.consumer.insert_batch")
    def test_reconnects_once_and_retries_same_batch(self, mock_insert):
        conn1, conn2 = MagicMock(name="conn1"), MagicMock(name="conn2")
        connect = MagicMock(side_effect=[conn1, conn2])
        sleep = MagicMock()
        mock_insert.side_effect = [psycopg2.OperationalError("server closed"), (2, 0)]

        writer = DbWriter(connect=connect, sleep=sleep)
        batch = self._batch()
        assert writer.write(batch) == (2, 0)

        assert connect.call_count == 2
        conn1.close.assert_called_once()
        assert mock_insert.call_args_list[0].args == (conn1, batch)
        assert mock_insert.call_args_list[1].args == (conn2, batch)
        sleep.assert_called_once_with(1)

    @patch("src.pipeline.consumer.insert_batch")
    def test_reconnect_failure_is_also_retried(self, mock_insert):
        """DB 가 아직 안 떠서 재접속(connect) 자체가 실패해도 다음 백오프로 넘어간다.
        (실제 docker stop 시 'could not translate host name' 으로 루프가 죽었던 케이스)"""
        conn1, conn3 = MagicMock(name="conn1"), MagicMock(name="conn3")
        connect = MagicMock(
            side_effect=[conn1, psycopg2.OperationalError("could not translate host name"), conn3]
        )
        sleep = MagicMock()
        mock_insert.side_effect = [psycopg2.OperationalError("server closed"), (2, 0)]

        writer = DbWriter(connect=connect, sleep=sleep)
        assert writer.write(self._batch()) == (2, 0)

        assert connect.call_count == 3
        assert [c.args[0] for c in sleep.call_args_list] == [1, 2]
        assert mock_insert.call_args_list[-1].args[0] is conn3

    @patch("src.pipeline.consumer.insert_batch")
    def test_gives_up_after_max_retries_with_backoff(self, mock_insert):
        """계속 실패하면 백오프(1,2,4,8,16s) 후 raise → 프로세스 재시작에 맡긴다.
        무한 재시도는 poll() 을 멈춰 max.poll.interval.ms 를 넘기므로 상한이 필요하다."""
        connect = MagicMock(side_effect=lambda: MagicMock())
        sleep = MagicMock()
        mock_insert.side_effect = psycopg2.InterfaceError("connection already closed")

        writer = DbWriter(connect=connect, sleep=sleep)
        try:
            writer.write(self._batch())
            assert False, "Should have raised"
        except psycopg2.InterfaceError:
            pass

        assert [c.args[0] for c in sleep.call_args_list] == [1, 2, 4, 8, 16]
        assert connect.call_count == 6  # 최초 1 + 재접속 5

    @patch("src.pipeline.consumer.insert_batch")
    def test_non_transient_error_is_not_retried(self, mock_insert):
        """데이터 자체 문제(DataError)는 재접속해도 똑같이 실패한다. 즉시 올린다."""
        connect = MagicMock(side_effect=lambda: MagicMock())
        sleep = MagicMock()
        mock_insert.side_effect = psycopg2.DataError("invalid input")

        writer = DbWriter(connect=connect, sleep=sleep)
        try:
            writer.write(self._batch())
            assert False, "Should have raised"
        except psycopg2.DataError:
            pass

        assert connect.call_count == 1
        sleep.assert_not_called()


def _kafka_error_msg(fatal: bool):
    err = MagicMock()
    err.fatal.return_value = fatal
    err.code.return_value = -999  # _PARTITION_EOF 아님
    err.__str__ = lambda self: "Broker transport failure"
    msg = MagicMock()
    msg.error.return_value = err
    return msg


class TestConsumeLoopKafkaErrors:
    @patch("src.pipeline.consumer.create_db_connection")
    @patch("src.pipeline.consumer.create_kafka_consumer")
    def test_non_fatal_kafka_error_keeps_loop_alive(
        self, mock_create_consumer, mock_create_db, caplog
    ):
        consumer = MagicMock()
        consumer.poll.side_effect = [_kafka_error_msg(fatal=False), None, KeyboardInterrupt()]
        mock_create_consumer.return_value = consumer

        with caplog.at_level("WARNING", logger="consumer"):
            consume_messages()

        assert "Kafka 메시지 오류" in caplog.text
        assert "Consumer 루프 오류" not in caplog.text
        assert consumer.poll.call_count == 3  # 에러 뒤에도 poll 을 계속했다

    @patch("src.pipeline.consumer.create_db_connection")
    @patch("src.pipeline.consumer.create_kafka_consumer")
    def test_fatal_kafka_error_stops_loop(
        self, mock_create_consumer, mock_create_db, caplog
    ):
        consumer = MagicMock()
        consumer.poll.side_effect = [_kafka_error_msg(fatal=True), None, KeyboardInterrupt()]
        mock_create_consumer.return_value = consumer

        with caplog.at_level("ERROR", logger="consumer"):
            consume_messages()

        assert "Consumer 루프 오류" in caplog.text
        assert consumer.poll.call_count == 1
