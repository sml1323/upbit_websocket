import os
import json
import logging
from datetime import datetime, timezone
from confluent_kafka import Consumer, KafkaException, KafkaError
from dotenv import load_dotenv
import psycopg2


load_dotenv()
KAFKA_SERVERS = os.getenv("KAFKA_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "upbit_ticker")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "default_group")
DB_NAME = os.getenv("TIMESCALEDB_DBNAME", "coin")
DB_USER = os.getenv("TIMESCALEDB_USER", "postgres")
DB_PASSWORD = os.getenv("TIMESCALEDB_PASSWORD", "postgres")
DB_HOST = os.getenv("TIMESCALEDB_HOST", "localhost")
DB_PORT = os.getenv("TIMESCALEDB_PORT", "5432")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def create_kafka_consumer():
    """
    Kafka 설정을 읽어와 Consumer 인스턴스를 생성합니다.
    
    - return: Kafka Consumer 인스턴스
    """
    config = {
        'bootstrap.servers': KAFKA_SERVERS,
        'group.id': KAFKA_GROUP_ID,
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': True,
    }
    try:
        consumer = Consumer(config)
        consumer.subscribe([KAFKA_TOPIC])
        logging.info(f"Consumer subscribed to topic '{KAFKA_TOPIC}' with group '{KAFKA_GROUP_ID}'")
        return consumer
    except Exception as e:
        logging.exception("Failed to create Kafka Consumer")
        raise e

def create_db_connection():
    """
    TimescaleDB에 연결합니다.
    """
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        logging.info("Connected to TimescaleDB.")
        return conn
    except Exception as e:
        logging.exception("Failed to connect to TimescaleDB.")
        raise e

def insert_trade_data(conn, data):
    """
    메시지 데이터에서 필요한 필드를 추출하여 TimescaleDB의 trade_data 테이블에 삽입합니다.
    - param conn: TimescaleDB 연결 객체
    - param data: Kafka 메시지에서 디코딩한 딕셔너리 데이터
    """
    try:
        # 업비트 ticker 메시지에서 trade_timestamp (ms 단위), code, trade_price, trade_volume 추출
        trade_ts = data.get("trade_timestamp")
        if trade_ts:
            ts = int(trade_ts)
            trade_time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        else:
            trade_time = datetime.now(timezone.utc)
        code = data.get("code", "unknown").replace("KRW-", "")
        trade_price = data.get("trade_price")
        trade_volume = data.get("trade_volume")
        
        cur = conn.cursor()
        query = """
            INSERT INTO trade_data (time, code, trade_price, trade_volume)
            VALUES (%s, %s, %s, %s)
        """
        cur.execute(query, (trade_time, code, trade_price, trade_volume))
        conn.commit()
        cur.close()
        logging.info(f"Inserted trade data: code={code}, time={trade_time}, price={trade_price}, volume={trade_volume}")
    except Exception as e:
        logging.exception("Failed to insert trade data.")
        conn.rollback()

def process_message(message, db_conn):
    """
    Kafka 메시지를 JSON 디코딩한 후, TimescaleDB에 저장합니다.
    
    :param message: Kafka 메시지 객체
    :param db_conn: TimescaleDB 연결 객체
    """
    try:
        data = json.loads(message.value().decode('utf-8'))
        logging.info(f"Received message: {data}")
        insert_trade_data(db_conn, data)
    except json.JSONDecodeError as e:
        logging.error(f"JSON decoding error: {e}")
    except Exception as e:
        logging.error(f"Error processing message: {e}")

def consume_messages():
    """
    Kafka 메시지를 소비하면서 TimescaleDB에 데이터를 저장합니다.
    """
    consumer = create_kafka_consumer()
    db_conn = create_db_connection()
    try:
        while True:
            msg = consumer.poll(1.0)  # 1초 대기 후 메시지 확인
            if msg is None:
                continue
            if msg.error():
                # 파티션의 끝에 도달한 경우
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logging.info(
                        "End of partition reached: {} [{}] at offset {}".format(
                            msg.topic(), msg.partition(), msg.offset()
                        )
                    )
                else:
                    raise KafkaException(msg.error())
            else:
                process_message(msg, db_conn)
    except KeyboardInterrupt:
        logging.info("Consumer interrupted by user")
    except Exception as e:
        logging.exception("Error in consumer loop")
    finally:
        consumer.close()
        db_conn.close()
        logging.info("Consumer and DB connection closed.")

def main():
    consume_messages()

if __name__ == "__main__":
    main()
