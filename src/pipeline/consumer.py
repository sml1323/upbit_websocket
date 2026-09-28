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

# DB 일시 장애 재시도: 1,2,4,8,16초 백오프 후 포기(총 ~31초).
# 무한 재시도는 poll() 을 멈춰 max.poll.interval.ms(기본 5분)를 넘기고 그룹에서 쫓겨난다.
MAX_DB_RETRIES = 5
DB_RETRY_BASE_SEC = 1
# 재접속하면 나을 수 있는 오류. DataError/IntegrityError 같은 데이터 문제는 여기 없다.
TRANSIENT_DB_ERRORS = (psycopg2.OperationalError, psycopg2.InterfaceError)


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
    # 당일(KST) 누적 거래량. 체결마다 단조 증가하므로 자연키의 일부:
    # Upbit 는 체결이 없어도 같은 ticker 를 다시 보내는데(SNAPSHOT→REALTIME, 호가 변동) 그건 값이 같고,
    # 같은 ms 에 난 서로 다른 체결은 값이 다르다.
    acc_trade_volume = data.get("acc_trade_volume")

    if trade_price is None or trade_volume is None or acc_trade_volume is None:
        return None

    return (trade_time, code, trade_price, trade_volume, acc_trade_volume)


def insert_batch(conn, batch: list[tuple]) -> tuple[int, int]:
    """배치를 tickers 에 적재하고 (inserted, skipped) 를 돌려준다.

    중복은 두 종류가 들어온다.
    - 파이프라인 재처리: "DB commit → Kafka offset commit" 사이에 죽으면 같은 배치가 다시 온다(at-least-once).
    - 소스 재전송: Upbit ticker 는 체결 없이도 같은 내용을 다시 보낸다(메시지의 약 40%).
    둘 다 (time, code, acc_trade_volume) UNIQUE 인덱스(db/init.sql)에 걸리므로 여기서 조용히 건너뛴다.

    재처리로 온 행은 내용까지 같은 중복이므로 DO NOTHING (덮어쓸 이유가 없다).
    """
    if not batch:
        return 0, 0
    query = """
        INSERT INTO tickers (time, code, trade_price, trade_volume, acc_trade_volume)
        VALUES %s
        ON CONFLICT (time, code, acc_trade_volume) DO NOTHING
    """
    try:
        with conn.cursor() as cur:
            # page_size=len(batch): execute_values 는 page_size 단위로 문장을 쪼개고
            # rowcount 는 마지막 문장 것만 남는다. 한 문장으로 보내야 실제 삽입 건수가 된다.
            execute_values(cur, query, batch, page_size=len(batch))
            inserted = cur.rowcount
        conn.commit()
        skipped = len(batch) - inserted
        logger.info("배치 INSERT 완료: %d건 (중복 스킵 %d건)", inserted, skipped)
        return inserted, skipped
    except Exception:
        logger.exception("배치 INSERT 실패, rollback")
        try:
            conn.rollback()
        except Exception:
            pass  # 커넥션이 이미 죽었으면 rollback 도 실패한다. 원래 예외를 살린다.
        raise


class DbWriter:
    """DB 커넥션을 들고 있다가, 일시 장애면 재접속해서 **같은 배치**를 다시 쓴다.

    호출 측은 배치를 메모리에 두고 offset 도 커밋하지 않은 상태라 재시도가 안전하고,
    성공 후 재처리가 겹쳐도 (time, code, acc_trade_volume) UNIQUE + ON CONFLICT 가 받아준다.
    """

    def __init__(self, connect=None, sleep=time.sleep):
        self._connect = connect or create_db_connection
        self._sleep = sleep
        self.conn = self._connect()

    def write(self, batch: list[tuple]) -> tuple[int, int]:
        for attempt in range(MAX_DB_RETRIES + 1):
            try:
                if self.conn is None:
                    # 재접속도 try 안에서: DB 가 아직 안 떠서 connect 가 실패해도 다음 백오프로 넘어간다.
                    self.conn = self._connect()
                return insert_batch(self.conn, batch)
            except TRANSIENT_DB_ERRORS as e:
                self._drop_conn()
                if attempt == MAX_DB_RETRIES:
                    logger.error("DB 재접속 %d회 실패, 포기", MAX_DB_RETRIES)
                    raise
                delay = DB_RETRY_BASE_SEC * 2**attempt
                logger.warning(
                    "DB 일시 장애(%s), %ds 후 재접속 (%d/%d)",
                    str(e).strip(), delay, attempt + 1, MAX_DB_RETRIES,
                )
                self._sleep(delay)
        raise RuntimeError("unreachable")

    def _drop_conn(self):
        if self.conn is None:
            return
        try:
            self.conn.close()
        except Exception:
            pass
        self.conn = None

    def close(self):
        self._drop_conn()


def consume_messages():
    consumer = create_kafka_consumer()
    db = DbWriter()
    batch: list[tuple] = []
    last_flush = time.monotonic()
    total_skipped = 0  # 프로세스 생애 동안 중복으로 건너뛴 건수 (재시작 직후 튀면 at-least-once 재처리 흔적)

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
                    elif msg.error().fatal():
                        # 클라이언트가 더 못 쓰는 상태(예: 멱등성 시퀀스 붕괴). 재시작만이 답.
                        raise KafkaException(msg.error())
                    else:
                        # 브로커 잠깐 끊김 등. librdkafka 가 알아서 재접속하니 다음 poll 로.
                        logger.warning("Kafka 메시지 오류(일시적): %s", msg.error())
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
                _, skipped = db.write(batch)
                consumer.commit()
                batch.clear()
                last_flush = time.monotonic()
                if skipped:
                    total_skipped += skipped
                    logger.info("누적 중복 스킵 %d건", total_skipped)

    except KeyboardInterrupt:
        logger.info("사용자에 의해 종료")
    except Exception:
        logger.exception("Consumer 루프 오류")
    finally:
        if batch:
            try:
                db.write(batch)
                consumer.commit()
            except Exception:
                logger.exception("최종 배치 flush 실패")
        consumer.close()
        db.close()
        logger.info("Consumer 및 DB 연결 종료")


def main():
    consume_messages()


if __name__ == "__main__":
    main()
