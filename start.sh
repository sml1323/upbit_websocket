#!/bin/bash

# Upbit Analytics Platform 통합 시작 스크립트
# 모든 서비스를 안전하게 시작하고 상태를 모니터링합니다.

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 시작 메시지
echo "================================================================"
echo "🚀 Upbit Analytics Platform Startup Script"
echo "================================================================"
echo ""

# 1. 환경 검증
log_step "1. Environment Validation"
if ! python shared/validate-env.py; then
    log_error "Environment validation failed! Please fix the issues and try again."
    exit 1
fi
log_info "Environment validation passed!"
echo ""

# 2. 기존 컨테이너 정리 (옵션)
if [[ "$1" == "--clean" ]]; then
    log_step "2. Cleaning up existing containers and volumes"
    docker compose down -v
    docker system prune -f
    log_info "Cleanup completed!"
else
    log_step "2. Stopping existing containers"
    docker compose down
    log_info "Existing containers stopped!"
fi
echo ""

# 3. 이미지 빌드
log_step "3. Building Docker images"
if [[ -f "shared/docker-build.sh" ]]; then
    chmod +x shared/docker-build.sh
    ./shared/docker-build.sh
else
    log_info "Building base image..."
    docker build -f shared/Dockerfile.python-base -t upbit-python-base:latest .
    
    log_info "Building service images..."
    docker compose build
fi
log_info "Docker images built successfully!"
echo ""

# 4. 인프라 서비스 시작
log_step "4. Starting infrastructure services"
log_info "Starting TimescaleDB, Zookeeper, Kafka, Redis..."
docker compose up -d timescaledb zookeeper kafka redis

# 인프라 서비스 대기
log_info "Waiting for infrastructure services to be ready..."
sleep 30

# 헬스체크
log_info "Checking infrastructure health..."
if ! docker compose ps timescaledb | grep -q "healthy"; then
    log_error "TimescaleDB is not healthy"
    docker logs timescaledb --tail=20
    exit 1
fi

if ! docker compose ps kafka | grep -q "healthy"; then
    log_error "Kafka is not healthy"
    docker logs kafka --tail=20
    exit 1
fi

log_info "Infrastructure services are ready!"
echo ""

# 5. 데이터 파이프라인 시작
log_step "5. Starting data pipeline"
log_info "Starting Upbit Producer and Consumer..."
docker compose up -d upbit-producer upbit-consumer

log_info "Waiting for data pipeline to be ready..."
sleep 15

# 데이터 파이프라인 상태 확인
if ! docker compose ps upbit-producer | grep -q "Up"; then
    log_error "Upbit Producer failed to start"
    docker logs upbit-producer --tail=20
    exit 1
fi

if ! docker compose ps upbit-consumer | grep -q "Up"; then
    log_error "Upbit Consumer failed to start"
    docker logs upbit-consumer --tail=20
    exit 1
fi

log_info "Data pipeline is running!"
echo ""

# 6. MVP 서비스 시작
log_step "6. Starting MVP services"
log_info "Starting Market Summary, Coin Q&A, and Anomaly Detection..."
docker compose up -d mvp-market-summary mvp-coin-qa mvp-anomaly-detection

log_info "Waiting for MVP services to be ready..."
sleep 20

# MVP 서비스 상태 확인
for service in mvp-market-summary mvp-coin-qa mvp-anomaly-detection; do
    if ! docker compose ps "$service" | grep -q "Up"; then
        log_error "$service failed to start"
        docker logs "$service" --tail=20
        exit 1
    fi
done

log_info "MVP services are running!"
echo ""

# 7. 대시보드 시작
log_step "7. Starting dashboard services"
log_info "Starting FastAPI Dashboard..."
docker compose up -d dashboard-server

log_info "Waiting for dashboard to be ready..."
sleep 10

if ! docker compose ps dashboard-server | grep -q "Up"; then
    log_error "Dashboard server failed to start"
    docker logs dashboard-server --tail=20
    exit 1
fi

log_info "Dashboard is running!"
echo ""

# 8. 시스템 상태 확인
log_step "8. System Status Check"
echo ""
echo "📊 Service Status:"
echo "===================="
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo ""

# 9. 데이터 수집 확인
log_step "9. Data Collection Check"
log_info "Checking data collection..."
sleep 5

# 간단한 데이터 확인
DATA_COUNT=$(docker exec timescaledb psql -U upbit_user -d upbit_analytics -t -c "SELECT COUNT(*) FROM ticker_data;" 2>/dev/null | tr -d ' ' || echo "0")
log_info "Current data records: $DATA_COUNT"

if [[ "$DATA_COUNT" -gt 0 ]]; then
    log_info "✅ Data collection is working!"
else
    log_warn "⚠️  No data found yet. Data collection might still be starting..."
fi
echo ""

# 10. 서비스 URL 표시
log_step "10. Service URLs"
echo ""
echo "🌐 Available Services:"
echo "======================"
echo "• FastAPI Dashboard:     http://localhost:8001"
echo "• API Documentation:     http://localhost:8001/docs"
echo "• Coin Q&A Service:      http://localhost:8080"
echo "• Market Summary (WS):   ws://localhost:8765"
echo "• React Dashboard:       http://localhost:3000 (manual start)"
echo "• TimescaleDB:           localhost:5432"
echo "• Kafka:                 localhost:9092"
echo "• Redis:                 localhost:6379"
echo ""

# 11. 헬스체크 스크립트 실행
log_step "11. Final Health Check"
if python shared/health-check.py system-check timescaledb kafka; then
    log_info "✅ All core services are healthy!"
else
    log_warn "⚠️  Some services might need more time to start"
fi
echo ""

# 12. 모니터링 안내
log_step "12. Monitoring Commands"
echo ""
echo "📋 Useful Commands:"
echo "==================="
echo "• View all logs:         docker compose logs -f"
echo "• View service status:   docker compose ps"
echo "• Stop all services:     docker compose down"
echo "• Restart service:       docker compose restart <service-name>"
echo "• View database:         docker exec -it timescaledb psql -U upbit_user -d upbit_analytics"
echo ""

# 완료 메시지
echo "================================================================"
echo "🎉 Upbit Analytics Platform Started Successfully!"
echo "================================================================"
echo ""
echo "The system is now running and collecting data from Upbit WebSocket."
echo "You can start using the services at the URLs listed above."
echo ""
echo "To stop the system, run: docker compose down"
echo "To view logs, run: docker compose logs -f"
echo ""

# React 대시보드 시작 안내
if [[ "$2" == "--start-react" ]]; then
    log_step "Starting React Dashboard"
    echo "Starting React development server..."
    cd dashboard-react
    npm run dev &
    REACT_PID=$!
    echo "React dashboard started at http://localhost:3000"
    echo "React PID: $REACT_PID"
    cd ..
fi

# 백그라운드 실행이 아닌 경우 로그 표시
if [[ "$1" != "--background" ]]; then
    echo "Press Ctrl+C to stop monitoring logs..."
    docker compose logs -f
fi