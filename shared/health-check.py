"""
Health check and dependency waiting utility for Upbit Analytics Platform
모든 서비스의 의존성 대기 및 헬스체크를 담당합니다.
"""

import os
import sys
import time
import logging
import requests
import psycopg2
from confluent_kafka import Consumer, KafkaError
from typing import Dict, List, Optional, Callable
import json

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HealthChecker:
    """헬스체크 및 의존성 대기 클래스"""
    
    def __init__(self, max_retries: int = 30, retry_delay: int = 5):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
    def wait_for_service(self, service_name: str, check_func: Callable, *args, **kwargs) -> bool:
        """서비스가 준비될 때까지 대기"""
        logger.info(f"Waiting for {service_name} to be ready...")
        
        for attempt in range(1, self.max_retries + 1):
            try:
                if check_func(*args, **kwargs):
                    logger.info(f"✅ {service_name} is ready!")
                    return True
                    
            except Exception as e:
                logger.debug(f"Attempt {attempt}/{self.max_retries} - {service_name} not ready: {e}")
                
            if attempt < self.max_retries:
                logger.info(f"⏳ Waiting {self.retry_delay}s before retry ({attempt}/{self.max_retries})...")
                time.sleep(self.retry_delay)
                
        logger.error(f"❌ {service_name} failed to become ready after {self.max_retries} attempts")
        return False
    
    def check_timescaledb(self, host: str = "localhost", port: int = 5432, 
                         user: str = "upbit_user", password: str = "upbit_password", 
                         database: str = "upbit_analytics") -> bool:
        """TimescaleDB 연결 확인"""
        try:
            conn = psycopg2.connect(
                host=host, port=port, user=user, password=password, database=database
            )
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
                
                # TimescaleDB extension 확인
                cur.execute("SELECT extname FROM pg_extension WHERE extname = 'timescaledb'")
                if not cur.fetchone():
                    logger.warning("TimescaleDB extension not found")
                    return False
                    
            conn.close()
            return True
            
        except Exception as e:
            logger.debug(f"TimescaleDB check failed: {e}")
            return False
    
    def check_kafka(self, bootstrap_servers: str = "localhost:9092", 
                   timeout: int = 10) -> bool:
        """Kafka 연결 확인"""
        try:
            consumer = Consumer({
                'bootstrap.servers': bootstrap_servers,
                'group.id': 'health-check-group',
                'auto.offset.reset': 'earliest'
            })
            
            # 메타데이터 요청으로 연결 확인
            metadata = consumer.list_topics(timeout=timeout)
            consumer.close()
            
            if not metadata.topics:
                logger.debug("No topics found in Kafka")
                return False
                
            return True
            
        except Exception as e:
            logger.debug(f"Kafka check failed: {e}")
            return False
    
    def check_http_service(self, url: str, timeout: int = 5) -> bool:
        """HTTP 서비스 확인"""
        try:
            response = requests.get(url, timeout=timeout)
            return response.status_code == 200
            
        except Exception as e:
            logger.debug(f"HTTP service check failed for {url}: {e}")
            return False
    
    def check_websocket_service(self, url: str, timeout: int = 5) -> bool:
        """WebSocket 서비스 확인 (HTTP 헬스체크 엔드포인트 사용)"""
        try:
            # WebSocket 서비스는 보통 HTTP 헬스체크 엔드포인트를 제공
            health_url = url.replace('ws://', 'http://').replace('wss://', 'https://')
            response = requests.get(health_url, timeout=timeout)
            return response.status_code == 200
            
        except Exception as e:
            logger.debug(f"WebSocket service check failed for {url}: {e}")
            return False
    
    def check_database_schema(self, host: str = "localhost", port: int = 5432, 
                            user: str = "upbit_user", password: str = "upbit_password", 
                            database: str = "upbit_analytics") -> bool:
        """데이터베이스 스키마 확인"""
        try:
            conn = psycopg2.connect(
                host=host, port=port, user=user, password=password, database=database
            )
            with conn.cursor() as cur:
                # 필수 테이블 확인
                required_tables = ['ticker_data']
                cur.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = ANY(%s)
                """, (required_tables,))
                
                existing_tables = [row[0] for row in cur.fetchall()]
                missing_tables = set(required_tables) - set(existing_tables)
                
                if missing_tables:
                    logger.warning(f"Missing tables: {missing_tables}")
                    return False
                
                # 필수 함수 확인
                required_functions = ['get_coin_summary', 'detect_anomalies', 'calculate_rsi']
                cur.execute("""
                    SELECT proname FROM pg_proc 
                    WHERE proname = ANY(%s) AND prokind = 'f'
                """, (required_functions,))
                
                existing_functions = [row[0] for row in cur.fetchall()]
                missing_functions = set(required_functions) - set(existing_functions)
                
                if missing_functions:
                    logger.warning(f"Missing functions: {missing_functions}")
                    return False
                    
            conn.close()
            return True
            
        except Exception as e:
            logger.debug(f"Database schema check failed: {e}")
            return False


def wait_for_dependencies(service_name: str, dependencies: List[str]) -> bool:
    """서비스 의존성 대기"""
    checker = HealthChecker()
    
    # 환경변수에서 설정 읽기
    db_host = os.getenv('TIMESCALEDB_HOST', 'localhost')
    db_port = int(os.getenv('TIMESCALEDB_PORT', '5432'))
    db_user = os.getenv('TIMESCALEDB_USER', 'upbit_user')
    db_password = os.getenv('TIMESCALEDB_PASSWORD', 'upbit_password')
    db_name = os.getenv('TIMESCALEDB_DBNAME', 'upbit_analytics')
    
    kafka_servers = os.getenv('KAFKA_SERVERS', 'localhost:9092')
    
    success = True
    
    for dependency in dependencies:
        if dependency == 'timescaledb':
            if not checker.wait_for_service(
                'TimescaleDB',
                checker.check_timescaledb,
                db_host, db_port, db_user, db_password, db_name
            ):
                success = False
                
        elif dependency == 'timescaledb-schema':
            if not checker.wait_for_service(
                'TimescaleDB Schema',
                checker.check_database_schema,
                db_host, db_port, db_user, db_password, db_name
            ):
                success = False
                
        elif dependency == 'kafka':
            if not checker.wait_for_service(
                'Kafka',
                checker.check_kafka,
                kafka_servers
            ):
                success = False
                
        elif dependency == 'dashboard-server':
            if not checker.wait_for_service(
                'Dashboard Server',
                checker.check_http_service,
                'http://localhost:8001/docs'
            ):
                success = False
                
        elif dependency == 'mvp-coin-qa':
            if not checker.wait_for_service(
                'MVP Coin QA',
                checker.check_http_service,
                'http://localhost:8080/docs'
            ):
                success = False
                
        elif dependency == 'mvp-market-summary':
            if not checker.wait_for_service(
                'MVP Market Summary',
                checker.check_http_service,
                'http://localhost:8765'
            ):
                success = False
                
        else:
            logger.warning(f"Unknown dependency: {dependency}")
    
    return success


def main():
    """메인 함수"""
    if len(sys.argv) < 2:
        logger.error("Usage: python health-check.py <service_name> [dependencies...]")
        sys.exit(1)
    
    service_name = sys.argv[1]
    dependencies = sys.argv[2:] if len(sys.argv) > 2 else []
    
    logger.info(f"Starting health check for {service_name}")
    logger.info(f"Dependencies: {dependencies}")
    
    if wait_for_dependencies(service_name, dependencies):
        logger.info(f"✅ All dependencies ready for {service_name}")
        sys.exit(0)
    else:
        logger.error(f"❌ Some dependencies failed for {service_name}")
        sys.exit(1)


if __name__ == "__main__":
    main()