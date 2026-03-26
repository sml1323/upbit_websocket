import json
from unittest.mock import patch, MagicMock

from src.pipeline.producer import KafkaProducerClient, get_coin_symbols


class TestKafkaProducerClient:
    @patch("src.pipeline.producer.Producer")
    def test_create_producer_uses_self_servers(self, mock_producer_cls):
        client = KafkaProducerClient(servers="my-server:9092", topic="test-topic")
        mock_producer_cls.assert_called_once_with(
            {"bootstrap.servers": "my-server:9092"}
        )
        assert client.topic == "test-topic"

    @patch("src.pipeline.producer.Producer")
    def test_send_increments_count(self, mock_producer_cls):
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer
        client = KafkaProducerClient(servers="localhost:9092", topic="test")

        client.send("BTC", {"price": 50000})
        assert client._send_count == 1
        mock_producer.produce.assert_called_once()
        mock_producer.poll.assert_called_once_with(0)

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

        client.close()
        mock_producer.flush.assert_called_once()


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
