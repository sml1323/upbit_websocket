import os
import json
import asyncio
import logging
import requests
import websockets
from confluent_kafka import Producer
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드
load_dotenv()
KAFKA_SERVERS = os.getenv("KAFKA_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "upbit_ticker")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def get_kafka_producer():
    """
    Kafka Producer 인스턴스를 생성하여 반환합니다.
    """
    config = {
        'bootstrap.servers': KAFKA_SERVERS,
    }
    try:
        producer = Producer(config)
        logging.info("Kafka Producer created.")
        return producer
    except Exception as e:
        logging.exception("Failed to create Kafka Producer.")
        raise e

def get_coin_symbols():
    """
    업비트 REST API를 통해 'KRW-'로 시작하는 코인 심볼 목록을 가져옵니다.
    
    :return: 코인 심볼 리스트
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

async def subscribe_upbit(producer):
    """
    업비트 웹소켓에 구독 요청을 보내고,
    수신한 ticker 메시지를 Kafka에 전송합니다.
    
    :param producer: Kafka Producer 인스턴스
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
                logging.info("WebSocket subscription started.")
                while True:
                    data = await websocket.recv()
                    message = json.loads(data)
                    # 메시지에 'code' 키가 없으면 'unknown' 사용
                    key = message.get("code", "unknown")
                    producer.produce(KAFKA_TOPIC, key=key, value=json.dumps(message))
                    # 즉시 전송을 위해 poll(0)
                    producer.poll(0)
                    logging.info(f"Sent message to Kafka with key: {key}")
        except websockets.ConnectionClosed as e:
            logging.warning(f"WebSocket connection closed: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"Error in WebSocket subscription: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

def main():
    """
    Kafka Producer를 생성하고, 업비트 웹소켓 구독 루프를 시작합니다.
    """
    producer = get_kafka_producer()
    try:
        asyncio.run(subscribe_upbit(producer))
    except KeyboardInterrupt:
        logging.info("Producer interrupted by user.")
    finally:
        producer.flush()
        logging.info("Producer flushed and closed.")

if __name__ == "__main__":
    main()
