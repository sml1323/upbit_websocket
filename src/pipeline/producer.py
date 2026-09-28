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


FLUSH_TIMEOUT_SEC = 10.0
BACKPRESSURE_POLL_SEC = 1.0


class KafkaProducerClient:
    """produce() 는 로컬 큐에 넣고 즉시 돌아온다. 브로커 도달 여부는 delivery 콜백으로만 안다.

    - _send_count: 브로커가 받았다고 확인해 준 건수 (콜백 성공)
    - _error_count: 재시도 소진·브로커 거부 등 최종 실패 건수 (콜백 실패)
    """

    def __init__(self, servers: str, topic: str):
        self.servers = servers
        self.topic = topic
        self.producer = self._create_producer()
        self._send_count = 0
        self._error_count = 0

    def _create_producer(self):
        config = {
            "bootstrap.servers": self.servers,
            # 멱등성: 재시도로 생기는 중복·재정렬을 브로커가 시퀀스 번호로 걸러낸다.
            # 켜면 librdkafka 가 acks=all, retries>0, max.in.flight<=5 를 자동 강제한다.
            "enable.idempotence": True,
            # 고빈도 소형 JSON 스트림: 살짝 모아서(linger) 압축해 보내는 편이 브로커·네트워크 비용이 낮다.
            "compression.type": "lz4",
            "linger.ms": 5,
        }
        try:
            producer = Producer(config)
            logger.info("Kafka Producer 생성 완료 (idempotent, lz4)")
            return producer
        except Exception:
            logger.exception("Kafka Producer 생성 실패")
            raise

    def _on_delivery(self, err, msg):
        """librdkafka 가 poll()/flush() 중에 호출한다. 전송 결과를 회수하는 유일한 지점."""
        if err is not None:
            self._error_count += 1
            logger.error("전송 실패: key=%s err=%s", msg.key(), err)
            return
        self._send_count += 1
        if self._send_count % 100 == 0:
            logger.info("%d건 전송 확인", self._send_count)

    def send(self, key: str, message: dict):
        value = json.dumps(message)
        try:
            try:
                self._produce(key, value)
            except BufferError:
                # 로컬 큐 가득 참: 잠깐 블로킹 poll 로 콜백을 소화해 자리를 만들고 한 번 더 시도.
                logger.warning("Producer 로컬 큐 가득 참, %.0fs poll 후 재시도", BACKPRESSURE_POLL_SEC)
                self.producer.poll(BACKPRESSURE_POLL_SEC)
                self._produce(key, value)
            self.producer.poll(0)  # 쌓인 delivery 콜백만 처리, 대기 없음
            logger.debug("메시지 적재: %s", key)
        except Exception as e:
            logger.error("메시지 적재 실패: %s", e)

    def _produce(self, key: str, value: str):
        self.producer.produce(
            self.topic, key=key, value=value, on_delivery=self._on_delivery
        )

    def close(self):
        remaining = self.producer.flush(timeout=FLUSH_TIMEOUT_SEC)
        if remaining:
            logger.warning("flush 타임아웃: %d건 미전송 (유실)", remaining)
        logger.info(
            "Producer 종료 (전송 확인 %d건, 실패 %d건, 미전송 %d건)",
            self._send_count, self._error_count, remaining,
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
