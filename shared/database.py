"""
Unified database connection module for Upbit LLM Analytics Platform
All services use this module to connect to TimescaleDB with consistent configuration
"""

import os
import logging
import psycopg2
from psycopg2 import pool
from typing import Optional, Dict, Any
from contextlib import contextmanager
import time

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Database configuration management"""
    
    def __init__(self):
        self.config = {
            'host': os.getenv('TIMESCALEDB_HOST', 'localhost'),
            'port': int(os.getenv('TIMESCALEDB_PORT', '5432')),
            'database': os.getenv('TIMESCALEDB_DBNAME', 'upbit_analytics'),
            'user': os.getenv('TIMESCALEDB_USER', 'upbit_user'),
            'password': os.getenv('TIMESCALEDB_PASSWORD', 'upbit_password'),
            'connect_timeout': int(os.getenv('DB_CONNECT_TIMEOUT', '10')),
            'options': '-c statement_timeout=30000'  # 30초 타임아웃
        }
        
    def get_connection_string(self) -> str:
        """Get connection string for psycopg2"""
        return (
            f"host={self.config['host']} "
            f"port={self.config['port']} "
            f"dbname={self.config['database']} "
            f"user={self.config['user']} "
            f"password={self.config['password']} "
            f"connect_timeout={self.config['connect_timeout']} "
            f"options='{self.config['options']}'"
        )


class DatabaseConnectionManager:
    """Database connection manager with pooling and retry logic"""
    
    def __init__(self, min_conn: int = 1, max_conn: int = 10):
        self.config = DatabaseConfig()
        self.connection_pool: Optional[pool.SimpleConnectionPool] = None
        self.min_conn = min_conn
        self.max_conn = max_conn
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                self.min_conn,
                self.max_conn,
                **self.config.config
            )
            logger.info(f"Database connection pool initialized (min={self.min_conn}, max={self.max_conn})")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise
    
    def get_connection(self, retry_count: int = 3, retry_delay: float = 1.0):
        """Get connection from pool with retry logic"""
        last_exception = None
        
        for attempt in range(retry_count):
            try:
                if self.connection_pool is None:
                    self._initialize_pool()
                
                conn = self.connection_pool.getconn()
                if conn:
                    # Test connection
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                    logger.debug(f"Database connection acquired (attempt {attempt + 1})")
                    return conn
                    
            except Exception as e:
                last_exception = e
                logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
                if attempt < retry_count - 1:
                    time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                    
        logger.error(f"Failed to get database connection after {retry_count} attempts")
        raise last_exception if last_exception else Exception("Unable to get database connection")
    
    def return_connection(self, conn):
        """Return connection to pool"""
        if self.connection_pool and conn:
            self.connection_pool.putconn(conn)
            logger.debug("Database connection returned to pool")
    
    def close_all_connections(self):
        """Close all connections in pool"""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("All database connections closed")
    
    @contextmanager
    def get_connection_context(self, retry_count: int = 3, retry_delay: float = 1.0):
        """Context manager for database connections"""
        conn = None
        try:
            conn = self.get_connection(retry_count, retry_delay)
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            if conn:
                self.return_connection(conn)


# Global connection manager instance
_db_manager: Optional[DatabaseConnectionManager] = None


def get_db_manager() -> DatabaseConnectionManager:
    """Get global database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseConnectionManager()
    return _db_manager


def get_db_connection(**kwargs):
    """Get database connection (legacy compatibility)"""
    return get_db_manager().get_connection(**kwargs)


def get_db_connection_context(**kwargs):
    """Get database connection context manager"""
    return get_db_manager().get_connection_context(**kwargs)


def create_db_connection():
    """Create single database connection (legacy compatibility)"""
    config = DatabaseConfig()
    return psycopg2.connect(**config.config)


# Health check function
def check_db_health() -> bool:
    """Check database connection health"""
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                return result is not None
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


if __name__ == "__main__":
    # Test database connection
    logging.basicConfig(level=logging.INFO)
    
    print("Testing database connection...")
    if check_db_health():
        print("✅ Database connection successful!")
    else:
        print("❌ Database connection failed!")
        
    # Test connection context
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                version = cur.fetchone()
                print(f"Database version: {version[0]}")
    except Exception as e:
        print(f"Error: {e}")