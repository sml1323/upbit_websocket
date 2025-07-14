import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from decimal import Decimal, InvalidOperation
from confluent_kafka import Consumer, KafkaException, KafkaError, Message
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import connection as Connection
from psycopg2 import sql

load_dotenv()

KAFKA_SERVERS = os.getenv("KAFKA_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "upbit_ticker")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "default_group")
DB_NAME = os.getenv("TIMESCALEDB_DBNAME", "coin")
DB_USER = os.getenv("TIMESCALEDB_USER", "postgres")
DB_PASSWORD = os.getenv("TIMESCALEDB_PASSWORD", "postgres")
DB_HOST = os.getenv("TIMESCALEDB_HOST", "localhost")
DB_PORT = os.getenv("TIMESCALEDB_PORT", "5432")

POLL_TIMEOUT = 1.0
INSERT_QUERY = """
    INSERT INTO ticker_data (
        time, code, type, opening_price, high_price, low_price, trade_price, 
        prev_closing_price, change, change_price, signed_change_price, 
        change_rate, signed_change_rate, trade_volume, acc_trade_volume, 
        acc_trade_price, ask_bid, acc_ask_volume, acc_bid_volume, 
        acc_trade_price_24h, acc_trade_volume_24h, highest_52_week_price, 
        highest_52_week_date, lowest_52_week_price, lowest_52_week_date, 
        market_state, market_warning, is_trading_suspended, delisting_date, 
        trade_date, trade_time, trade_timestamp, timestamp, stream_type
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
"""

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def create_kafka_consumer() -> Consumer:
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
        raise

def create_db_connection() -> Connection:
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
        raise

def parse_date_string(date_str: str) -> Optional[str]:
    """Parse date string from format YYYY-MM-DD to DATE type."""
    try:
        if date_str and len(date_str) == 10:
            return date_str
        return None
    except:
        return None

def insert_ticker_data(conn: Connection, data: Dict[str, Any]) -> None:
    """Insert complete ticker data with all 22 fields."""
    try:
        # Parse timestamp - use trade_timestamp as primary time source
        trade_ts = data.get("trade_timestamp")
        if trade_ts:
            ts = int(trade_ts)
            time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        else:
            time = datetime.now(timezone.utc)
        
        # Extract all fields with proper type conversion and validation
        values = (
            time,  # time
            data.get("code", "UNKNOWN"),  # code (keep KRW- prefix)
            data.get("type", "ticker"),  # type
            float(data.get("opening_price", 0)),  # opening_price
            float(data.get("high_price", 0)),  # high_price
            float(data.get("low_price", 0)),  # low_price
            float(data.get("trade_price", 0)),  # trade_price
            float(data.get("prev_closing_price", 0)),  # prev_closing_price
            data.get("change", "EVEN"),  # change (ENUM)
            float(data.get("change_price", 0)),  # change_price
            float(data.get("signed_change_price", 0)),  # signed_change_price
            float(data.get("change_rate", 0)),  # change_rate
            float(data.get("signed_change_rate", 0)),  # signed_change_rate
            float(data.get("trade_volume", 0)),  # trade_volume
            float(data.get("acc_trade_volume", 0)),  # acc_trade_volume
            float(data.get("acc_trade_price", 0)),  # acc_trade_price
            data.get("ask_bid", "BID"),  # ask_bid (ENUM)
            float(data.get("acc_ask_volume", 0)),  # acc_ask_volume
            float(data.get("acc_bid_volume", 0)),  # acc_bid_volume
            float(data.get("acc_trade_price_24h", 0)),  # acc_trade_price_24h
            float(data.get("acc_trade_volume_24h", 0)),  # acc_trade_volume_24h
            float(data.get("highest_52_week_price", 0)),  # highest_52_week_price
            parse_date_string(data.get("highest_52_week_date")),  # highest_52_week_date
            float(data.get("lowest_52_week_price", 0)),  # lowest_52_week_price
            parse_date_string(data.get("lowest_52_week_date")),  # lowest_52_week_date
            data.get("market_state", "ACTIVE"),  # market_state (ENUM)
            data.get("market_warning", "NONE"),  # market_warning (ENUM)
            bool(data.get("is_trading_suspended", False)),  # is_trading_suspended
            parse_date_string(data.get("delisting_date")),  # delisting_date (nullable)
            data.get("trade_date", ""),  # trade_date (string)
            data.get("trade_time", ""),  # trade_time (string)
            int(data.get("trade_timestamp", 0)),  # trade_timestamp (bigint)
            int(data.get("timestamp", 0)),  # timestamp (bigint)
            data.get("stream_type", "REALTIME")  # stream_type (ENUM)
        )
        
        with conn.cursor() as cur:
            cur.execute(INSERT_QUERY, values)
            conn.commit()
        
        code = data.get("code", "UNKNOWN")
        trade_price = data.get("trade_price", 0)
        change_rate = data.get("change_rate", 0)
        
        logging.info(f"Inserted ticker data: {code} @ {trade_price} ({change_rate:+.4f}%)")
        
    except Exception as e:
        logging.exception(f"Failed to insert ticker data: {e}")
        logging.error(f"Problematic data: {data}")
        conn.rollback()
        raise

def process_message(message: Message, db_conn: Connection) -> None:
    try:
        data = json.loads(message.value().decode('utf-8'))
        
        # Log only essential info to reduce noise
        code = data.get("code", "UNKNOWN")
        trade_price = data.get("trade_price", 0)
        change_rate = data.get("change_rate", 0)
        logging.debug(f"Processing: {code} @ {trade_price} ({change_rate:+.4f}%)")
        
        insert_ticker_data(db_conn, data)
        
    except json.JSONDecodeError as e:
        logging.error(f"JSON decoding error: {e}")
        logging.error(f"Raw message: {message.value().decode('utf-8')}")
    except Exception as e:
        logging.error(f"Error processing message: {e}")
        logging.error(f"Message data: {data if 'data' in locals() else 'N/A'}")

def consume_messages() -> None:
    consumer = create_kafka_consumer()
    db_conn = create_db_connection()
    
    try:
        while True:
            msg = consumer.poll(POLL_TIMEOUT)
            if msg is None:
                continue
                
            if msg.error():
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

def main() -> None:
    consume_messages()

if __name__ == "__main__":
    main()
