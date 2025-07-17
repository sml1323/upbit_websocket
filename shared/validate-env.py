"""
Environment validation script for Upbit Analytics Platform
환경 설정 검증 및 필수 조건 확인을 담당합니다.
"""

import os
import sys
import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import subprocess
import socket

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """검증 결과 클래스"""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class EnvironmentValidator:
    """환경 설정 검증 클래스"""
    
    def __init__(self):
        self.required_env_vars = {
            'database': [
                'TIMESCALEDB_HOST', 'TIMESCALEDB_PORT', 'TIMESCALEDB_DBNAME',
                'TIMESCALEDB_USER', 'TIMESCALEDB_PASSWORD'
            ],
            'kafka': [
                'KAFKA_SERVERS', 'KAFKA_TOPIC', 'KAFKA_GROUP_ID'
            ],
            'openai': [
                'OPENAI_API_KEY'
            ]
        }
        
        self.port_requirements = {
            'timescaledb': 5432,
            'kafka': 9092,
            'zookeeper': 2181,
            'redis': 6379,
            'dashboard': 8001,
            'coin_qa': 8080,
            'market_summary': 8765
        }
    
    def validate_environment_variables(self) -> ValidationResult:
        """환경 변수 검증"""
        missing_vars = []
        
        for category, vars_list in self.required_env_vars.items():
            for var in vars_list:
                if not os.getenv(var):
                    missing_vars.append(f"{category}: {var}")
        
        if missing_vars:
            return ValidationResult(
                success=False,
                message=f"Missing required environment variables: {', '.join(missing_vars)}",
                details={'missing_vars': missing_vars}
            )
        
        return ValidationResult(
            success=True,
            message="All required environment variables are set",
            details={'checked_vars': sum(len(vars_list) for vars_list in self.required_env_vars.values())}
        )
    
    def validate_openai_api_key(self) -> ValidationResult:
        """OpenAI API 키 검증"""
        api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            return ValidationResult(
                success=False,
                message="OPENAI_API_KEY not set"
            )
        
        if not api_key.startswith('sk-'):
            return ValidationResult(
                success=False,
                message="Invalid OpenAI API key format (should start with 'sk-')"
            )
        
        if len(api_key) < 48:
            return ValidationResult(
                success=False,
                message="OpenAI API key seems too short"
            )
        
        return ValidationResult(
            success=True,
            message="OpenAI API key format is valid"
        )
    
    def validate_docker_environment(self) -> ValidationResult:
        """Docker 환경 검증"""
        try:
            # Docker 명령어 실행 가능 여부 확인
            result = subprocess.run(['docker', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return ValidationResult(
                    success=False,
                    message="Docker is not installed or not accessible"
                )
            
            docker_version = result.stdout.strip()
            
            # Docker Compose 명령어 확인
            result = subprocess.run(['docker', 'compose', 'version'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return ValidationResult(
                    success=False,
                    message="Docker Compose is not installed or not accessible"
                )
            
            compose_version = result.stdout.strip()
            
            return ValidationResult(
                success=True,
                message="Docker environment is ready",
                details={
                    'docker_version': docker_version,
                    'compose_version': compose_version
                }
            )
            
        except subprocess.TimeoutExpired:
            return ValidationResult(
                success=False,
                message="Docker command timed out"
            )
        except Exception as e:
            return ValidationResult(
                success=False,
                message=f"Docker check failed: {str(e)}"
            )
    
    def validate_port_availability(self) -> ValidationResult:
        """포트 사용 가능성 검증"""
        unavailable_ports = []
        
        for service, port in self.port_requirements.items():
            if self.is_port_in_use(port):
                unavailable_ports.append(f"{service}:{port}")
        
        if unavailable_ports:
            return ValidationResult(
                success=False,
                message=f"Ports already in use: {', '.join(unavailable_ports)}",
                details={'unavailable_ports': unavailable_ports}
            )
        
        return ValidationResult(
            success=True,
            message="All required ports are available",
            details={'checked_ports': len(self.port_requirements)}
        )
    
    def is_port_in_use(self, port: int, host: str = 'localhost') -> bool:
        """포트 사용 여부 확인"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                return result == 0
        except Exception:
            return False
    
    def validate_python_dependencies(self) -> ValidationResult:
        """Python 의존성 검증"""
        required_packages = [
            'confluent-kafka', 'psycopg2-binary', 'websockets', 
            'python-dotenv', 'requests', 'openai', 'fastapi', 'uvicorn'
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            return ValidationResult(
                success=False,
                message=f"Missing Python packages: {', '.join(missing_packages)}",
                details={'missing_packages': missing_packages}
            )
        
        return ValidationResult(
            success=True,
            message="All required Python packages are installed",
            details={'checked_packages': len(required_packages)}
        )
    
    def validate_filesystem_permissions(self) -> ValidationResult:
        """파일시스템 권한 검증"""
        required_dirs = [
            'shared/', 'schema/', 'upbit-kafka/', 'mvp-services/', 
            'dashboard/', 'dashboard-react/'
        ]
        
        missing_dirs = []
        unreadable_dirs = []
        
        for dir_path in required_dirs:
            if not os.path.exists(dir_path):
                missing_dirs.append(dir_path)
            elif not os.access(dir_path, os.R_OK):
                unreadable_dirs.append(dir_path)
        
        if missing_dirs or unreadable_dirs:
            return ValidationResult(
                success=False,
                message=f"Directory issues - Missing: {missing_dirs}, Unreadable: {unreadable_dirs}",
                details={
                    'missing_dirs': missing_dirs,
                    'unreadable_dirs': unreadable_dirs
                }
            )
        
        return ValidationResult(
            success=True,
            message="All required directories are accessible",
            details={'checked_dirs': len(required_dirs)}
        )
    
    def run_full_validation(self) -> bool:
        """전체 검증 실행"""
        logger.info("🔍 Starting environment validation...")
        
        validations = [
            ("Environment Variables", self.validate_environment_variables),
            ("OpenAI API Key", self.validate_openai_api_key),
            ("Docker Environment", self.validate_docker_environment),
            ("Port Availability", self.validate_port_availability),
            ("Python Dependencies", self.validate_python_dependencies),
            ("Filesystem Permissions", self.validate_filesystem_permissions),
        ]
        
        all_passed = True
        
        for name, validation_func in validations:
            logger.info(f"Validating {name}...")
            
            try:
                result = validation_func()
                
                if result.success:
                    logger.info(f"✅ {name}: {result.message}")
                    if result.details:
                        logger.debug(f"Details: {result.details}")
                else:
                    logger.error(f"❌ {name}: {result.message}")
                    if result.details:
                        logger.error(f"Details: {result.details}")
                    all_passed = False
                    
            except Exception as e:
                logger.error(f"❌ {name}: Validation failed with error: {str(e)}")
                all_passed = False
        
        if all_passed:
            logger.info("🎉 All validations passed! Environment is ready.")
        else:
            logger.error("💥 Some validations failed. Please fix the issues before proceeding.")
        
        return all_passed
    
    def generate_env_template(self) -> str:
        """환경 변수 템플릿 생성"""
        template = "# Upbit Analytics Platform Environment Configuration\n\n"
        
        for category, vars_list in self.required_env_vars.items():
            template += f"# {category.upper()} Configuration\n"
            
            for var in vars_list:
                current_value = os.getenv(var, "")
                if var == 'OPENAI_API_KEY':
                    template += f"{var}=your_openai_api_key_here\n"
                elif 'PASSWORD' in var:
                    template += f"{var}=your_secure_password_here\n"
                elif current_value:
                    template += f"{var}={current_value}\n"
                else:
                    template += f"{var}=\n"
            
            template += "\n"
        
        return template


def main():
    """메인 함수"""
    validator = EnvironmentValidator()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--generate-template':
        print(validator.generate_env_template())
        return
    
    success = validator.run_full_validation()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()