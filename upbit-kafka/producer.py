import os
import json
import asyncio
import logging
import requests
import websockets
from typing import List, Dict, Any
from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()

KAFKA_SERVERS = os.getenv("KAFKA_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "upbit_ticker")
UPBIT_API_URL = "https://api.upbit.com/v1/market/all"
UPBIT_WS_URL = "wss://api.upbit.com/websocket/v1"
RECONNECT_DELAY = 5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
class KafkaProducerClient:
    def __init__(self, servers: str, topic: str) -> None:
        self.servers = servers
        self.topic = topic
        self.producer = self._create_producer()

    def _create_producer(self) -> Producer:
        config = {
            'bootstrap.servers': self.servers,
        }
        try:
            producer = Producer(config)
            logging.info("카프카 프로듀서 생성")
            return producer
        except Exception as e:
            logging.exception("카프카 프로듀서 생성 실패")
            raise
    def send(self, key: str, message: Dict[str, Any]) -> None:
        try:
            self.producer.produce(self.topic, key=key, value=json.dumps(message))
            self.producer.poll(0)
            logging.info(f"{key} 키로 카프카에 메세지 전송")
        except Exception as e:
            logging.error(f"카프카로 메세지 전송 실패: {e}")
    
    def close(self) -> None:
        self.producer.flush()
        logging.info("Kafka Producer flushed and closed.")






def get_coin_symbols() -> List[str]:
    try:
        response = requests.get(UPBIT_API_URL)
        response.raise_for_status()
        markets = response.json()
        symbols = [market['market'] for market in markets if market['market'].startswith("KRW-")]
        logging.info(f"Fetched {len(symbols)} coin symbols from Upbit.")
        return symbols
    except Exception as e:
        logging.exception("Failed to fetch coin symbols.")
        raise

async def subscribe_upbit(producer: KafkaProducerClient) -> None:
    coin_symbols = get_coin_symbols()
    
    while True:
        try:
            async with websockets.connect(UPBIT_WS_URL) as websocket:
                subscribe_data = [
                    {"ticket": "test"},
                    {"type": "ticker", "codes": coin_symbols}
                ]
                await websocket.send(json.dumps(subscribe_data))
                logging.info("웹소켓 구독 시작!")
                
                while True:
                    data = await websocket.recv()
                    message = json.loads(data)
                    key = message.get("code", "unknown")
                    producer.send(key=key, message=message)
        
        except websockets.ConnectionClosed as e:
            logging.warning(f"웹소켓 연결 종료: {e}. Reconnecting in {RECONNECT_DELAY} seconds...")
            await asyncio.sleep(RECONNECT_DELAY)
        except Exception as e:
            logging.error(f"웹소켓 구독 오류: {e}. Retrying in {RECONNECT_DELAY} seconds...")
            await asyncio.sleep(RECONNECT_DELAY)

def main() -> None:
    producer = KafkaProducerClient(servers=KAFKA_SERVERS, topic=KAFKA_TOPIC)

    try:
        asyncio.run(subscribe_upbit(producer))
    except KeyboardInterrupt:
        logging.info("Producer interrupted by user.")
    finally:
        producer.close()
        logging.info("Producer flushed and closed.")

if __name__ == "__main__":
    main()
