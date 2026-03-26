import json
import asyncio

import requests
import websockets
from confluent_kafka import Producer

from src.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC,
    UPBIT_WS_URL,
    UPBIT_API_URL,
    setup_logging,
)

logger = setup_logging("producer")


class KafkaProducerClient:
    def __init__(self, servers: str, topic: str):
        self.servers = servers
        self.topic = topic
        self.producer = self._create_producer()
        self._send_count = 0

    def _create_producer(self):
        config = {"bootstrap.servers": self.servers}
        try:
            producer = Producer(config)
            logger.info("Kafka Producer 생성 완료")
            return producer
        except Exception as e:
            logger.exception("Kafka Producer 생성 실패")
            raise

    def send(self, key: str, message: dict):
        try:
            self.producer.produce(
                self.topic, key=key, value=json.dumps(message)
            )
            self.producer.poll(0)
            self._send_count += 1
            logger.debug("메시지 전송: %s", key)
            if self._send_count % 100 == 0:
                logger.info("%d건 전송 완료", self._send_count)
        except Exception as e:
            logger.error("메시지 전송 실패: %s", e)

    def close(self):
        self.producer.flush()
        logger.info(
            "Producer 종료 (총 %d건 전송)", self._send_count
        )


def get_coin_symbols() -> list:
    url = f"{UPBIT_API_URL}/market/all"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        markets = response.json()
        symbols = [
            m["market"] for m in markets if m["market"].startswith("KRW-")
        ]
        logger.info("코인 심볼 %d개 조회", len(symbols))
        return symbols
    except Exception:
        logger.exception("코인 심볼 조회 실패")
        raise


async def subscribe_upbit(producer: KafkaProducerClient):
    coin_symbols = get_coin_symbols()
    while True:
        try:
            async with websockets.connect(UPBIT_WS_URL) as websocket:
                subscribe_data = [
                    {"ticket": "upbit-ticker"},
                    {"type": "ticker", "codes": coin_symbols},
                ]
                await websocket.send(json.dumps(subscribe_data))
                logger.info("WebSocket 구독 시작 (%d 코인)", len(coin_symbols))
                while True:
                    data = await websocket.recv()
                    message = json.loads(data)
                    key = message.get("code", "unknown")
                    producer.send(key=key, message=message)
        except websockets.ConnectionClosed as e:
            logger.warning("WebSocket 연결 종료: %s. 5초 후 재연결...", e)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error("WebSocket 오류: %s. 5초 후 재시도...", e)
            await asyncio.sleep(5)


def main():
    producer = KafkaProducerClient(
        servers=KAFKA_BOOTSTRAP_SERVERS, topic=KAFKA_TOPIC
    )
    try:
        asyncio.run(subscribe_upbit(producer))
    except KeyboardInterrupt:
        logger.info("사용자에 의해 종료")
    finally:
        producer.close()


if __name__ == "__main__":
    main()
