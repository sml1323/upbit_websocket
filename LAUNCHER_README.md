# 🚀 Upbit Analytics Platform 통합 실행 시스템

단일 명령으로 전체 Upbit Analytics Platform을 실행할 수 있는 통합 스크립트 시스템입니다.

## 📋 주요 스크립트

### 1. 메인 런처: `launch-upbit-analytics.sh`
전체 시스템을 한 번에 시작하는 메인 스크립트입니다.

```bash
# 기본 사용법 (minimal 모드)
./launch-upbit-analytics.sh

# 전체 서비스 실행
./launch-upbit-analytics.sh --full

# 개발 모드
./launch-upbit-analytics.sh --dev

# 실행 계획만 확인 (실제 실행 안함)
./launch-upbit-analytics.sh --dry-run --full

# 도움말
./launch-upbit-analytics.sh --help
```

**실행 모드**:
- `--minimal`: 핵심 서비스만 (DB + 데이터수집 + Q&A)
- `--dev`: 개발 모드 (핵심 + 분석 서비스)
- `--prod`: 운영 모드 (백그라운드 실행)
- `--full`: 전체 모드 (모든 서비스 + MCP서버 + Next.js)

### 2. 상태 확인: `scripts/health-check.sh`
모든 서비스의 상태를 확인합니다.

```bash
# 전체 상태 확인
./scripts/health-check.sh

# 인프라만 확인
./scripts/health-check.sh infrastructure

# 개별 서비스 확인
./scripts/health-check.sh service timescaledb

# 도움말
./scripts/health-check.sh help
```

### 3. 로그 관리: `scripts/logs.sh`
통합 로그 관리 시스템입니다.

```bash
# 대화형 로그 탐색기
./scripts/logs.sh

# 특정 서비스 로그 보기
./scripts/logs.sh show timescaledb

# 에러 로그만 보기
./scripts/logs.sh errors

# 실시간 로그 추적
./scripts/logs.sh follow upbit-producer

# 도움말
./scripts/logs.sh help
```

### 4. 안전한 종료: `scripts/stop-all.sh`
모든 서비스를 안전하게 종료합니다.

```bash
# 정상 종료 (데이터 안전성 보장)
./scripts/stop-all.sh

# 강제 종료 (빠름, 데이터 손실 위험)
./scripts/stop-all.sh --force

# 로그 백업 후 종료
./scripts/stop-all.sh --export-logs

# 도움말
./scripts/stop-all.sh --help
```

## 🎯 사용 시나리오

### 첫 실행
```bash
# 1. 환경 검증 및 최소 서비스 실행
./launch-upbit-analytics.sh --minimal

# 2. 상태 확인
./scripts/health-check.sh

# 3. 필요시 전체 서비스 실행
./scripts/stop-all.sh
./launch-upbit-analytics.sh --full
```

### 개발 중
```bash
# 1. 개발 모드 실행
./launch-upbit-analytics.sh --dev

# 2. 로그 모니터링
./scripts/logs.sh follow upbit-producer

# 3. 문제 발생 시 에러 로그 확인
./scripts/logs.sh errors
```

### 문제 해결
```bash
# 1. 전체 상태 확인
./scripts/health-check.sh

# 2. 개별 서비스 상태 확인
./scripts/health-check.sh service kafka

# 3. 특정 서비스 로그 확인
./scripts/logs.sh show kafka --lines 100

# 4. 시스템 재시작
./scripts/stop-all.sh
./launch-upbit-analytics.sh --full
```

## 🛠 시스템 아키텍처

### 의존성 순서 (시작)
1. **인프라**: TimescaleDB, Zookeeper, Kafka, Redis
2. **데이터 파이프라인**: upbit-producer, upbit-consumer  
3. **분석 서비스**: mvp-coin-qa, mvp-market-summary, mvp-anomaly-detection, dashboard-server
4. **선택적 서비스**: mcp-server, dashboard-react

### 종료 순서 (역순)
1. **선택적 서비스**: dashboard-react, mcp-server
2. **분석 서비스**: dashboard-server, mvp-anomaly-detection, mvp-market-summary, mvp-coin-qa
3. **데이터 파이프라인**: upbit-consumer, upbit-producer
4. **인프라**: kafka, zookeeper, redis, timescaledb

## 🔧 설정 및 환경

### 필수 요구사항
- Docker & Docker Compose
- Bash 3.2+ (macOS 호환)
- 포트 가용성: 5432, 9092, 8080, 8765, 8001, 3000, 9093
- 디스크 공간: 최소 5GB
- 메모리: 최소 2GB

### 환경변수 (.env 파일)
```bash
KAFKA_SERVERS=localhost:9092
KAFKA_TOPIC=upbit_ticker
KAFKA_GROUP_ID=default_group
TIMESCALEDB_HOST=localhost
TIMESCALEDB_PORT=5432
TIMESCALEDB_DB=upbit_analytics
TIMESCALEDB_USER=upbit_user
TIMESCALEDB_PASSWORD=upbit_password
OPENAI_API_KEY=your_openai_api_key
```

## 📊 서비스 접속 정보

실행 완료 후 다음 서비스에 접속할 수 있습니다:

- **Coin Q&A**: http://localhost:8080
- **Market Summary**: ws://localhost:8765
- **Dashboard**: http://localhost:8001
- **Next.js App**: http://localhost:3000 (--full 모드)
- **TimescaleDB**: localhost:5432
- **MCP Server**: localhost:9093 (--full 모드)

## ⚠️ 중요 사항

### 데이터 안전성
- `./scripts/stop-all.sh`는 데이터 무결성을 보장합니다
- 강제 종료(`--force`)는 데이터 손실 위험이 있습니다
- `--remove-volumes` 옵션은 모든 데이터를 영구 삭제합니다

### 문제 해결
1. **포트 충돌**: 다른 서비스가 해당 포트를 사용 중인지 확인
2. **Docker 문제**: `docker system prune -f` 후 재시도
3. **메모리 부족**: 불필요한 컨테이너 중지 후 재시도
4. **네트워크 문제**: Docker 네트워크 설정 확인

### 로그 및 디버깅
- 로그는 `./scripts/logs.sh`로 확인
- 문제 발생 시 `--export-logs` 옵션으로 로그 백업
- 상세 로그는 `--verbose` 옵션 사용

## 🎉 완료!

이제 `./launch-upbit-analytics.sh`로 전체 Upbit Analytics Platform을 한 번에 실행할 수 있습니다!

문제나 질문이 있으면 각 스크립트의 `--help` 옵션을 확인해주세요.