import os
import json
import asyncio
import logging
import requests
import websockets
from confluent_kafka import Producer
from dotenv import load_dotenv
df
# .env 파일에서 환경변수 로드
load_dotenv()
KAFKA_SERVERS = os.getenv("KAFKA_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "upbit_ticker")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
class KafkaProducerClient():
    def __init__(self, servers:str, topic:str):
        """
        Kafka Producer 인스턴스를 생성하고 관리하는 클래스
        - servers: Kafka 서버 주소
        - topic: Kafka 토픽
        """
        self.servers = servers
        self.topic = topic
        self.producer = self._create_producer()

    def _create_producer(self):
        """Kafka 인스턴스 생성"""
        config = {
            'bootstrap.servers': KAFKA_SERVERS,
            }
        try:
            producer = Producer(config)
            logging.info("카프카 프로듀서 생성")
            return producer
        except Exception as e:
            logging.exception("카프카 프로듀서 생성 실패")
            raise e
    def send(self, key: str, message: dict):
        """
        Kafka로 메세지를 전송하는 메서드

        - key: Kafka 메세지 키
        - message: Kafka로 전송할 메세지 - dict
        """
        try:
            self.producer.produce(self.topic, key=key, value=json.dumps(message))
            self.producer.poll(0)
            logging.info(f"{key} 키로 카프카에 메세지 전송")
        except Exception as e:
            logging.error(f"카프카로 메세지 전송 실패: {e}")
    
    def close(self):
        """Kafka Producer 종료."""
        self.producer.flush()
        logging.info("Kafka Producer flushed and closed.")






def get_coin_symbols() -> list:
    """
    업비트 REST API를 통해 'KRW-'로 시작하는 코인 심볼 목록을 가져옵니다.
    
    - return: 코인 심볼 리스트
    """
    url = "https://api.upbit.com/v1/market/all"
    try:
        response = requests.get(url)
        response.raise_for_status()
        markets = response.json()
        symbols = [market['market'] for market in markets if market['market'].startswith("KRW-")]
        logging.info(f"Fetched {len(symbols)} coin symbols from Upbit.")
        return symbols
    except Exception as e:
        logging.exception("Failed to fetch coin symbols.")
        raise e

async def subscribe_upbit(producer: KafkaProducerClient):
    """
    업비트 웹소켓에 구독 요청을 보내고,
    수신한 ticker 메시지를 Kafka에 전송합니다.
    
    - producer: Kafka Producer 인스턴스
    """
    coin_symbols = get_coin_symbols()
    ws_uri = "wss://api.upbit.com/websocket/v1"
    while True:
        try:
            async with websockets.connect(ws_uri) as websocket:
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
            logging.warning(f"웹소켓 연결 종료: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"웹소켓 구독 오류: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

def main():
    """
    Kafka Producer를 생성하고, 업비트 웹소켓 구독 루프를 시작합니다.
    """
    producer = KafkaProducerClient(servers=KAFKA_SERVERS, topic=KAFKA_TOPIC)

    try:
        asyncio.run(subscribe_upbit(producer))
    except KeyboardInterrupt:
        logging.info("Producer interrupted by user.")
    finally:
        producer.flush()
        logging.info("Producer flushed and closed.")

if __name__ == "__main__":
    main()
