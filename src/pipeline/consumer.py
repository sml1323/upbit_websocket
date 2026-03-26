import json
import time
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_values
from confluent_kafka import Consumer, KafkaException, KafkaError

from src.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC,
    BATCH_SIZE,
    BATCH_TIMEOUT_SEC,
    get_db_dsn,
    setup_logging,
)

logger = setup_logging("consumer")

KAFKA_GROUP_ID = "upbit-consumer-group"


def create_kafka_consumer() -> Consumer:
    config = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": KAFKA_GROUP_ID,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    }
    consumer = Consumer(config)
    consumer.subscribe([KAFKA_TOPIC])
    logger.info("Kafka Consumer 구독 시작: topic=%s", KAFKA_TOPIC)
    return consumer


def create_db_connection():
    conn = psycopg2.connect(get_db_dsn())
    logger.info("TimescaleDB 연결 완료")
    return conn


def parse_ticker_message(data: dict) -> tuple | None:
    trade_ts = data.get("trade_timestamp")
    if trade_ts:
        ts = int(trade_ts)
        trade_time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    else:
        trade_time = datetime.now(timezone.utc)

    code = data.get("code", "unknown").replace("KRW-", "")
    trade_price = data.get("trade_price")
    trade_volume = data.get("trade_volume")

    if trade_price is None or trade_volume is None:
        return None

    return (trade_time, code, trade_price, trade_volume)


def insert_batch(conn, batch: list[tuple]):
    if not batch:
        return
    query = """
        INSERT INTO tickers (time, code, trade_price, trade_volume)
        VALUES %s
    """
    try:
        with conn.cursor() as cur:
            execute_values(cur, query, batch)
        conn.commit()
        logger.info("배치 INSERT 완료: %d건", len(batch))
    except Exception:
        logger.exception("배치 INSERT 실패, rollback")
        conn.rollback()
        raise


def consume_messages():
    consumer = create_kafka_consumer()
    db_conn = create_db_connection()
    batch: list[tuple] = []
    last_flush = time.monotonic()

    try:
        while True:
            msg = consumer.poll(0.1)

            if msg is not None:
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug(
                            "파티션 끝 도달: %s [%d] offset %d",
                            msg.topic(),
                            msg.partition(),
                            msg.offset(),
                        )
                    else:
                        raise KafkaException(msg.error())
                else:
                    try:
                        data = json.loads(msg.value().decode("utf-8"))
                        row = parse_ticker_message(data)
                        if row:
                            batch.append(row)
                            logger.debug("메시지 수신: %s", row[1])
                    except json.JSONDecodeError as e:
                        logger.error("JSON 디코딩 오류: %s", e)

            elapsed = time.monotonic() - last_flush
            if len(batch) >= BATCH_SIZE or (batch and elapsed >= BATCH_TIMEOUT_SEC):
                insert_batch(db_conn, batch)
                consumer.commit()
                batch.clear()
                last_flush = time.monotonic()

    except KeyboardInterrupt:
        logger.info("사용자에 의해 종료")
    except Exception:
        logger.exception("Consumer 루프 오류")
    finally:
        if batch:
            try:
                insert_batch(db_conn, batch)
                consumer.commit()
            except Exception:
                logger.exception("최종 배치 flush 실패")
        consumer.close()
        db_conn.close()
        logger.info("Consumer 및 DB 연결 종료")


def main():
    consume_messages()


if __name__ == "__main__":
    main()
