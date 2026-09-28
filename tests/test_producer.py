import json
from unittest.mock import patch, MagicMock

from src.pipeline.producer import KafkaProducerClient, get_coin_symbols


class TestKafkaProducerClient:
    @patch("src.pipeline.producer.Producer")
    def test_create_producer_uses_self_servers(self, mock_producer_cls):
        client = KafkaProducerClient(servers="my-server:9092", topic="test-topic")
        config = mock_producer_cls.call_args.args[0]
        assert config["bootstrap.servers"] == "my-server:9092"
        assert client.topic == "test-topic"

    @patch("src.pipeline.producer.Producer")
    def test_create_producer_enables_idempotence_and_compression(self, mock_producer_cls):
        """멱등성(중복·재정렬 방지)과 압축·linger(고빈도 스트림 처리량)를 명시한다."""
        KafkaProducerClient(servers="s:9092", topic="t")
        config = mock_producer_cls.call_args.args[0]
        assert config["enable.idempotence"] is True
        assert config["compression.type"] == "lz4"
        assert config["linger.ms"] > 0

    @patch("src.pipeline.producer.Producer")
    def test_send_produces_and_polls_without_counting_yet(self, mock_producer_cls):
        """produce() 는 로컬 큐 적재일 뿐이라 전송 성공으로 세지 않는다."""
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer
        client = KafkaProducerClient(servers="localhost:9092", topic="test")

        client.send("BTC", {"price": 50000})
        assert client._send_count == 0
        mock_producer.produce.assert_called_once()
        mock_producer.poll.assert_called_once_with(0)

    @patch("src.pipeline.producer.Producer")
    def test_delivery_success_increments_send_count(self, mock_producer_cls):
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer
        client = KafkaProducerClient(servers="localhost:9092", topic="test")

        client.send("BTC", {"price": 50000})
        on_delivery = mock_producer.produce.call_args.kwargs["on_delivery"]
        on_delivery(None, MagicMock())
        assert client._send_count == 1
        assert client._error_count == 0

    @patch("src.pipeline.producer.Producer")
    def test_delivery_failure_counts_and_logs_error(self, mock_producer_cls, caplog):
        """브로커 거부·재시도 소진은 콜백으로만 알 수 있다. 조용히 잃지 않는다."""
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer
        client = KafkaProducerClient(servers="localhost:9092", topic="test")

        client.send("BTC", {"price": 50000})
        on_delivery = mock_producer.produce.call_args.kwargs["on_delivery"]
        msg = MagicMock()
        msg.key.return_value = b"BTC"
        with caplog.at_level("ERROR", logger="producer"):
            on_delivery(MagicMock(__str__=lambda self: "Message timed out"), msg)
        assert client._send_count == 0
        assert client._error_count == 1
        assert "전송 실패" in caplog.text and "Message timed out" in caplog.text

    @patch("src.pipeline.producer.Producer")
    def test_buffer_error_drains_queue_then_retries_once(self, mock_producer_cls):
        """로컬 큐가 가득 차면(BufferError) poll 로 콜백을 소화해 자리를 만들고 재시도한다."""
        mock_producer = MagicMock()
        mock_producer.produce.side_effect = [BufferError("queue full"), None]
        mock_producer_cls.return_value = mock_producer
        client = KafkaProducerClient(servers="localhost:9092", topic="test")

        client.send("BTC", {"price": 50000})
        assert mock_producer.produce.call_count == 2
        blocking_polls = [c for c in mock_producer.poll.call_args_list if c.args and c.args[0] > 0]
        assert len(blocking_polls) == 1

    @patch("src.pipeline.producer.Producer")
    def test_send_handles_exception(self, mock_producer_cls):
        mock_producer = MagicMock()
        mock_producer.produce.side_effect = Exception("Kafka down")
        mock_producer_cls.return_value = mock_producer
        client = KafkaProducerClient(servers="localhost:9092", topic="test")

        # Should not raise
        client.send("BTC", {"price": 50000})
        assert client._send_count == 0

    @patch("src.pipeline.producer.Producer")
    def test_close_flushes(self, mock_producer_cls):
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer
        client = KafkaProducerClient(servers="localhost:9092", topic="test")

        mock_producer.flush.return_value = 0
        client.close()
        mock_producer.flush.assert_called_once()
        assert mock_producer.flush.call_args.kwargs.get("timeout", 0) > 0

    @patch("src.pipeline.producer.Producer")
    def test_close_warns_about_undelivered_messages(self, mock_producer_cls, caplog):
        """flush(timeout) 은 미전송 건수를 돌려준다. 0 이 아니면 유실이다."""
        mock_producer = MagicMock()
        mock_producer.flush.return_value = 3
        mock_producer_cls.return_value = mock_producer
        client = KafkaProducerClient(servers="localhost:9092", topic="test")

        with caplog.at_level("WARNING", logger="producer"):
            client.close()
        assert "3건 미전송" in caplog.text


class TestGetCoinSymbols:
    @patch("src.pipeline.producer.requests.get")
    def test_returns_krw_symbols(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"market": "KRW-BTC"},
            {"market": "KRW-ETH"},
            {"market": "BTC-ETH"},
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        symbols = get_coin_symbols()
        assert symbols == ["KRW-BTC", "KRW-ETH"]

    @patch("src.pipeline.producer.requests.get")
    def test_raises_on_api_failure(self, mock_get):
        mock_get.side_effect = Exception("API down")
        try:
            get_coin_symbols()
            assert False, "Should have raised"
        except Exception:
            pass
