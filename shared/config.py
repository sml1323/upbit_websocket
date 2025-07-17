"""
Shared configuration module for Upbit LLM Analytics Platform
All services use this module for consistent configuration management
"""

import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration"""
    host: str
    port: int
    database: str
    user: str
    password: str
    connect_timeout: int = 10
    min_pool_size: int = 1
    max_pool_size: int = 10


@dataclass
class KafkaConfig:
    """Kafka configuration"""
    bootstrap_servers: str
    topic: str
    group_id: str
    auto_offset_reset: str = 'latest'
    enable_auto_commit: bool = True


@dataclass
class OpenAIConfig:
    """OpenAI configuration"""
    api_key: str
    model: str = "gpt-4o-mini"
    max_tokens: int = 1000
    temperature: float = 0.7


@dataclass
class ServiceConfig:
    """Service-specific configuration"""
    name: str
    port: int
    host: str = "0.0.0.0"
    debug: bool = False
    log_level: str = "INFO"


class ConfigManager:
    """Central configuration manager"""
    
    def __init__(self):
        self._database_config: Optional[DatabaseConfig] = None
        self._kafka_config: Optional[KafkaConfig] = None
        self._openai_config: Optional[OpenAIConfig] = None
        self._service_configs: Dict[str, ServiceConfig] = {}
    
    @property
    def database(self) -> DatabaseConfig:
        """Get database configuration"""
        if self._database_config is None:
            self._database_config = DatabaseConfig(
                host=os.getenv('TIMESCALEDB_HOST', 'localhost'),
                port=int(os.getenv('TIMESCALEDB_PORT', '5432')),
                database=os.getenv('TIMESCALEDB_DBNAME', 'upbit_analytics'),
                user=os.getenv('TIMESCALEDB_USER', 'upbit_user'),
                password=os.getenv('TIMESCALEDB_PASSWORD', 'upbit_password'),
                connect_timeout=int(os.getenv('DB_CONNECT_TIMEOUT', '10')),
                min_pool_size=int(os.getenv('DB_MIN_POOL_SIZE', '1')),
                max_pool_size=int(os.getenv('DB_MAX_POOL_SIZE', '10'))
            )
        return self._database_config
    
    @property
    def kafka(self) -> KafkaConfig:
        """Get Kafka configuration"""
        if self._kafka_config is None:
            self._kafka_config = KafkaConfig(
                bootstrap_servers=os.getenv('KAFKA_SERVERS', 'localhost:9092'),
                topic=os.getenv('KAFKA_TOPIC', 'upbit_ticker'),
                group_id=os.getenv('KAFKA_GROUP_ID', 'default_group'),
                auto_offset_reset=os.getenv('KAFKA_AUTO_OFFSET_RESET', 'latest'),
                enable_auto_commit=os.getenv('KAFKA_ENABLE_AUTO_COMMIT', 'true').lower() == 'true'
            )
        return self._kafka_config
    
    @property
    def openai(self) -> OpenAIConfig:
        """Get OpenAI configuration"""
        if self._openai_config is None:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                logger.warning("OPENAI_API_KEY not found in environment variables")
            
            self._openai_config = OpenAIConfig(
                api_key=api_key or "",
                model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
                max_tokens=int(os.getenv('OPENAI_MAX_TOKENS', '1000')),
                temperature=float(os.getenv('OPENAI_TEMPERATURE', '0.7'))
            )
        return self._openai_config
    
    def get_service_config(self, service_name: str) -> ServiceConfig:
        """Get service-specific configuration"""
        if service_name not in self._service_configs:
            # Default port mapping
            port_mapping = {
                'producer': 8001,
                'consumer': 8002,
                'market_summary': 8765,
                'coin_qa': 8080,
                'anomaly_detection': 8003,
                'dashboard': 8001,
                'mcp_server': 9093
            }
            
            self._service_configs[service_name] = ServiceConfig(
                name=service_name,
                port=int(os.getenv(f'{service_name.upper()}_PORT', port_mapping.get(service_name, 8000))),
                host=os.getenv(f'{service_name.upper()}_HOST', '0.0.0.0'),
                debug=os.getenv(f'{service_name.upper()}_DEBUG', 'false').lower() == 'true',
                log_level=os.getenv(f'{service_name.upper()}_LOG_LEVEL', 'INFO')
            )
            
        return self._service_configs[service_name]
    
    def is_docker_env(self) -> bool:
        """Check if running in Docker environment"""
        return os.getenv('DOCKER_ENV', 'false').lower() == 'true'
    
    def get_env_info(self) -> Dict[str, Any]:
        """Get environment information"""
        return {
            'is_docker': self.is_docker_env(),
            'database_host': self.database.host,
            'kafka_servers': self.kafka.bootstrap_servers,
            'openai_configured': bool(self.openai.api_key),
            'log_level': os.getenv('LOG_LEVEL', 'INFO')
        }


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def setup_logging(service_name: str):
    """Setup logging configuration for service"""
    config = get_config()
    service_config = config.get_service_config(service_name)
    
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=getattr(logging, service_config.log_level),
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f'/tmp/{service_name}.log') if config.is_docker_env() 
            else logging.FileHandler(f'{service_name}.log')
        ]
    )
    
    logger.info(f"Logging configured for {service_name} (level: {service_config.log_level})")


if __name__ == "__main__":
    # Test configuration
    config = get_config()
    
    print("=== Configuration Test ===")
    print(f"Database: {config.database.host}:{config.database.port}")
    print(f"Kafka: {config.kafka.bootstrap_servers}")
    print(f"OpenAI configured: {bool(config.openai.api_key)}")
    print(f"Docker environment: {config.is_docker_env()}")
    
    # Test service configurations
    for service in ['producer', 'consumer', 'market_summary', 'coin_qa']:
        svc_config = config.get_service_config(service)
        print(f"{service}: {svc_config.host}:{svc_config.port}")
    
    print("\n=== Environment Info ===")
    env_info = config.get_env_info()
    for key, value in env_info.items():
        print(f"{key}: {value}")