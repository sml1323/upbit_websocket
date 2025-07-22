#!/bin/bash

# =============================================================================
# Upbit Analytics Platform - Health Check System
# =============================================================================
# Comprehensive health check functions for all platform services
# Dependencies: utils.sh for logging and output functions
# =============================================================================

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source utility functions
source "$SCRIPT_DIR/utils.sh"

# =============================================================================
# Health Check Constants
# =============================================================================

readonly DEFAULT_TIMEOUT=30
readonly HTTP_TIMEOUT=15
readonly DB_TIMEOUT=10

# Service definitions - bash 3.2 compatible
get_service_info() {
    case "$1" in
        "timescaledb") echo "TimescaleDB:5432" ;;
        "zookeeper") echo "Zookeeper:2181" ;;
        "kafka") echo "Kafka:9092" ;;
        "redis") echo "Redis:6379" ;;
        "upbit-producer") echo "Upbit Producer:WebSocket" ;;
        "upbit-consumer") echo "Data Consumer:Background" ;;
        "mvp-coin-qa") echo "Coin Q&A:8080" ;;
        "mvp-market-summary") echo "Market Summary:8765" ;;
        "mvp-anomaly-detection") echo "Anomaly Detection:Background" ;;
        "dashboard-server") echo "Dashboard:8001" ;;
        "mcp-server") echo "MCP Server:9093" ;;
        "dashboard-react") echo "Next.js Dashboard:3000" ;;
    esac
}

# =============================================================================
# Infrastructure Health Checks
# =============================================================================

check_timescaledb_health() {
    local timeout=${1:-$DB_TIMEOUT}
    
    print_progress "TimescaleDB 상태 확인 중..."
    
    # Container 상태 확인
    if ! docker ps --format "table {{.Names}}" | grep -q "^timescaledb$"; then
        print_error "TimescaleDB 컨테이너가 실행 중이지 않습니다"
        return 1
    fi
    
    # PostgreSQL 연결 테스트
    local cmd="docker exec timescaledb pg_isready -U upbit_user -d upbit_analytics -h localhost -p 5432"
    if timeout "$timeout" $cmd >/dev/null 2>&1; then
        print_success "TimescaleDB 연결 정상"
    else
        print_error "TimescaleDB 연결 실패"
        return 1
    fi
    
    # 데이터베이스 스키마 확인
    local schema_check="docker exec timescaledb psql -U upbit_user -d upbit_analytics -c \"SELECT COUNT(*) FROM ticker_data LIMIT 1;\" -t"
    if timeout "$timeout" $schema_check >/dev/null 2>&1; then
        print_success "TimescaleDB 스키마 정상"
        
        # 최근 데이터 확인
        local data_count=$(docker exec timescaledb psql -U upbit_user -d upbit_analytics -c "SELECT COUNT(*) FROM ticker_data WHERE timestamp > NOW() - INTERVAL '5 minutes';" -t 2>/dev/null | tr -d ' ')
        if [ -n "$data_count" ] && [ "$data_count" -gt 0 ]; then
            print_success "최근 데이터 수신 확인됨 (${data_count}건)"
        else
            print_warning "최근 5분간 새로운 데이터가 없습니다"
        fi
    else
        print_warning "TimescaleDB 스키마 확인 실패"
    fi
    
    return 0
}

check_kafka_health() {
    local timeout=${1:-$DEFAULT_TIMEOUT}
    
    print_progress "Kafka 상태 확인 중..."
    
    # Container 상태 확인
    if ! docker ps --format "table {{.Names}}" | grep -q "kafka"; then
        print_error "Kafka 컨테이너가 실행 중이지 않습니다"
        return 1
    fi
    
    # Kafka 브로커 연결 테스트
    local cmd="docker exec kafka kafka-topics.sh --list --bootstrap-server localhost:9092"
    if timeout "$timeout" $cmd >/dev/null 2>&1; then
        print_success "Kafka 브로커 연결 정상"
    else
        print_error "Kafka 브로커 연결 실패"
        return 1
    fi
    
    # Topic 존재 확인
    local topic_check="docker exec kafka kafka-topics.sh --list --bootstrap-server localhost:9092 | grep -q upbit_ticker"
    if timeout "$timeout" $topic_check >/dev/null 2>&1; then
        print_success "Kafka Topic 'upbit_ticker' 존재 확인"
    else
        print_warning "Kafka Topic 'upbit_ticker'가 존재하지 않습니다"
    fi
    
    return 0
}

check_zookeeper_health() {
    local timeout=${1:-$DEFAULT_TIMEOUT}
    
    print_progress "Zookeeper 상태 확인 중..."
    
    # Container 상태 확인
    if ! docker ps --format "table {{.Names}}" | grep -q "zookeeper"; then
        print_error "Zookeeper 컨테이너가 실행 중이지 않습니다"
        return 1
    fi
    
    # Zookeeper 연결 테스트 (포트 2181 확인)
    if timeout "$timeout" docker exec zookeeper nc -z localhost 2181 >/dev/null 2>&1; then
        print_success "Zookeeper 연결 정상"
    else
        print_error "Zookeeper 연결 실패"
        return 1
    fi
    
    return 0
}

check_redis_health() {
    local timeout=${1:-$DEFAULT_TIMEOUT}
    
    print_progress "Redis 상태 확인 중..."
    
    # Container 상태 확인
    if ! docker ps --format "table {{.Names}}" | grep -q "redis"; then
        print_error "Redis 컨테이너가 실행 중이지 않습니다"
        return 1
    fi
    
    # Redis 연결 테스트
    local cmd="docker exec redis redis-cli ping"
    if timeout "$timeout" $cmd | grep -q "PONG"; then
        print_success "Redis 연결 정상"
    else
        print_error "Redis 연결 실패"
        return 1
    fi
    
    return 0
}

# =============================================================================
# Data Pipeline Health Checks  
# =============================================================================

check_upbit_producer_health() {
    local timeout=${1:-$DEFAULT_TIMEOUT}
    
    print_progress "Upbit Producer 상태 확인 중..."
    
    # Container 상태 확인
    if ! docker ps --format "table {{.Names}}" | grep -q "upbit-producer"; then
        print_error "Upbit Producer 컨테이너가 실행 중이지 않습니다"
        return 1
    fi
    
    # 프로세스 로그에서 WebSocket 연결 확인
    local log_check="docker logs upbit-producer --tail 10 2>/dev/null | grep -i 'connected\\|websocket\\|ticker' | tail -1"
    local recent_log=$(eval "$log_check")
    
    if [ -n "$recent_log" ]; then
        print_success "Upbit Producer WebSocket 연결 활성"
    else
        print_warning "Upbit Producer 연결 상태를 확인할 수 없습니다"
    fi
    
    return 0
}

check_upbit_consumer_health() {
    local timeout=${1:-$DEFAULT_TIMEOUT}
    
    print_progress "Data Consumer 상태 확인 중..."
    
    # Container 상태 확인
    if ! docker ps --format "table {{.Names}}" | grep -q "upbit-consumer"; then
        print_error "Data Consumer 컨테이너가 실행 중이지 않습니다"
        return 1
    fi
    
    # 최근 로그에서 데이터 처리 확인
    local log_check="docker logs upbit-consumer --tail 5 2>/dev/null | grep -i 'processed\\|inserted\\|saved' | tail -1"
    local recent_log=$(eval "$log_check")
    
    if [ -n "$recent_log" ]; then
        print_success "Data Consumer 데이터 처리 정상"
    else
        print_warning "Data Consumer 처리 상태를 확인할 수 없습니다"
    fi
    
    return 0
}

# =============================================================================
# MVP Services Health Checks
# =============================================================================

check_coin_qa_health() {
    local timeout=${1:-$HTTP_TIMEOUT}
    
    print_progress "Coin Q&A 시스템 상태 확인 중..."
    
    # Container 상태 확인
    if ! docker ps --format "table {{.Names}}" | grep -q "mvp-coin-qa"; then
        print_error "Coin Q&A 컨테이너가 실행 중이지 않습니다"
        return 1
    fi
    
    # HTTP 헬스체크 (포트 8080)
    local health_url="http://localhost:8080/health"
    if timeout "$timeout" curl -sf "$health_url" >/dev/null 2>&1; then
        print_success "Coin Q&A HTTP 서비스 정상"
    else
        # Fallback: 포트 확인
        if netstat -tuln 2>/dev/null | grep -q ":8080 "; then
            print_success "Coin Q&A 포트 8080 바인딩됨"
        else
            print_error "Coin Q&A HTTP 서비스 응답 실패"
            return 1
        fi
    fi
    
    return 0
}

check_market_summary_health() {
    local timeout=${1:-$HTTP_TIMEOUT}
    
    print_progress "Market Summary 서비스 상태 확인 중..."
    
    # Container 상태 확인
    if ! docker ps --format "table {{.Names}}" | grep -q "mvp-market-summary"; then
        print_error "Market Summary 컨테이너가 실행 중이지 않습니다"
        return 1
    fi
    
    # WebSocket 포트 확인 (8765)
    if netstat -tuln 2>/dev/null | grep -q ":8765 "; then
        print_success "Market Summary WebSocket 서버 정상 (8765)"
    else
        print_error "Market Summary WebSocket 서버 응답 실패"
        return 1
    fi
    
    return 0
}

check_anomaly_detection_health() {
    local timeout=${1:-$DEFAULT_TIMEOUT}
    
    print_progress "Anomaly Detection 시스템 상태 확인 중..."
    
    # Container 상태 확인
    if ! docker ps --format "table {{.Names}}" | grep -q "mvp-anomaly-detection"; then
        print_error "Anomaly Detection 컨테이너가 실행 중이지 않습니다"
        return 1
    fi
    
    # 최근 로그에서 이상 탐지 활동 확인
    local log_check="docker logs mvp-anomaly-detection --tail 5 2>/dev/null | grep -i 'anomaly\\|alert\\|detection' | tail -1"
    local recent_log=$(eval "$log_check")
    
    if [ -n "$recent_log" ]; then
        print_success "Anomaly Detection 정상 작동"
    else
        print_warning "Anomaly Detection 활동을 확인할 수 없습니다"
    fi
    
    return 0
}

check_dashboard_health() {
    local timeout=${1:-$HTTP_TIMEOUT}
    
    print_progress "Dashboard 서버 상태 확인 중..."
    
    # Container 상태 확인
    if ! docker ps --format "table {{.Names}}" | grep -q "dashboard-server"; then
        print_error "Dashboard 컨테이너가 실행 중이지 않습니다"
        return 1
    fi
    
    # HTTP 헬스체크 (포트 8001)
    local health_url="http://localhost:8001"
    if timeout "$timeout" curl -sf "$health_url" >/dev/null 2>&1; then
        print_success "Dashboard HTTP 서비스 정상"
    else
        # Fallback: 포트 확인
        if netstat -tuln 2>/dev/null | grep -q ":8001 "; then
            print_success "Dashboard 포트 8001 바인딩됨"
        else
            print_error "Dashboard HTTP 서비스 응답 실패"
            return 1
        fi
    fi
    
    return 0
}

# =============================================================================
# Optional Services Health Checks
# =============================================================================

check_mcp_server_health() {
    local timeout=${1:-$HTTP_TIMEOUT}
    
    print_progress "MCP Server 상태 확인 중..."
    
    # Container 상태 확인
    if ! docker ps --format "table {{.Names}}" | grep -q "mcp-server"; then
        print_warning "MCP Server 컨테이너가 실행 중이지 않습니다 (선택적 서비스)"
        return 1
    fi
    
    # 포트 9093 확인
    if netstat -tuln 2>/dev/null | grep -q ":9093 "; then
        print_success "MCP Server 포트 9093 바인딩됨"
    else
        print_warning "MCP Server 포트 9093 응답 없음"
        return 1
    fi
    
    return 0
}

check_nextjs_health() {
    local timeout=${1:-$HTTP_TIMEOUT}
    
    print_progress "Next.js Dashboard 상태 확인 중..."
    
    # Container 상태 확인
    if ! docker ps --format "table {{.Names}}" | grep -q "dashboard-react"; then
        print_warning "Next.js Dashboard 컨테이너가 실행 중이지 않습니다 (선택적 서비스)"
        return 1
    fi
    
    # HTTP 헬스체크 (포트 3000)
    local health_url="http://localhost:3000"
    if timeout "$timeout" curl -sf "$health_url" >/dev/null 2>&1; then
        print_success "Next.js Dashboard HTTP 서비스 정상"
    else
        print_warning "Next.js Dashboard HTTP 서비스 응답 실패"
        return 1
    fi
    
    return 0
}

# =============================================================================
# Comprehensive Health Check Functions
# =============================================================================

check_infrastructure_health() {
    print_header "인프라 서비스 상태 확인"
    
    local failed_services=0
    
    check_timescaledb_health || ((failed_services++))
    check_zookeeper_health || ((failed_services++))
    check_kafka_health || ((failed_services++))
    check_redis_health || ((failed_services++))
    
    echo
    if [ $failed_services -eq 0 ]; then
        print_success "모든 인프라 서비스가 정상입니다"
        return 0
    else
        print_error "$failed_services개 인프라 서비스에 문제가 있습니다"
        return 1
    fi
}

check_data_pipeline_health() {
    print_header "데이터 파이프라인 상태 확인"
    
    local failed_services=0
    
    check_upbit_producer_health || ((failed_services++))
    check_upbit_consumer_health || ((failed_services++))
    
    echo
    if [ $failed_services -eq 0 ]; then
        print_success "데이터 파이프라인이 정상입니다"
        return 0
    else
        print_error "$failed_services개 데이터 파이프라인 서비스에 문제가 있습니다"
        return 1
    fi
}

check_analytics_services_health() {
    print_header "분석 서비스 상태 확인"
    
    local failed_services=0
    
    check_coin_qa_health || ((failed_services++))
    check_market_summary_health || ((failed_services++))
    check_anomaly_detection_health || ((failed_services++))
    check_dashboard_health || ((failed_services++))
    
    echo
    if [ $failed_services -eq 0 ]; then
        print_success "모든 분석 서비스가 정상입니다"
        return 0
    else
        print_error "$failed_services개 분석 서비스에 문제가 있습니다"
        return 1
    fi
}

check_optional_services_health() {
    print_header "선택적 서비스 상태 확인"
    
    local failed_services=0
    local total_services=2
    
    check_mcp_server_health || ((failed_services++))
    check_nextjs_health || ((failed_services++))
    
    echo
    local running_services=$((total_services - failed_services))
    print_info "$running_services/$total_services 선택적 서비스가 실행 중입니다"
    
    return 0
}

# =============================================================================
# Overall Health Check
# =============================================================================

run_full_health_check() {
    print_header "🚀 Upbit Analytics Platform 전체 상태 확인"
    
    local total_failures=0
    
    # 1. 인프라 서비스
    check_infrastructure_health || ((total_failures++))
    echo
    
    # 2. 데이터 파이프라인  
    check_data_pipeline_health || ((total_failures++))
    echo
    
    # 3. 분석 서비스
    check_analytics_services_health || ((total_failures++))
    echo
    
    # 4. 선택적 서비스
    check_optional_services_health
    echo
    
    # 5. 전체 요약
    print_header "전체 상태 요약"
    
    if [ $total_failures -eq 0 ]; then
        print_success "${EMOJI_SUCCESS} 모든 핵심 서비스가 정상 작동합니다!"
        
        # 데이터 통계 표시
        show_data_statistics
        show_service_urls
        
        return 0
    else
        print_error "${EMOJI_ERROR} $total_failures개 서비스 그룹에 문제가 있습니다"
        echo
        print_info "문제 해결 방법:"
        print_info "• 개별 서비스 로그 확인: ./scripts/logs.sh [service-name]"
        print_info "• 서비스 재시작: docker-compose restart [service-name]"
        print_info "• 전체 시스템 재시작: ./scripts/stop-all.sh && ./launch-upbit-analytics.sh"
        
        return 1
    fi
}

show_data_statistics() {
    print_info "📊 데이터 현황:"
    
    # TimescaleDB에서 데이터 통계 가져오기
    local total_records=$(docker exec timescaledb psql -U upbit_user -d upbit_analytics -c "SELECT COUNT(*) FROM ticker_data;" -t 2>/dev/null | tr -d ' ' || echo "N/A")
    local unique_coins=$(docker exec timescaledb psql -U upbit_user -d upbit_analytics -c "SELECT COUNT(DISTINCT market) FROM ticker_data;" -t 2>/dev/null | tr -d ' ' || echo "N/A")
    local recent_data=$(docker exec timescaledb psql -U upbit_user -d upbit_analytics -c "SELECT COUNT(*) FROM ticker_data WHERE timestamp > NOW() - INTERVAL '1 hour';" -t 2>/dev/null | tr -d ' ' || echo "N/A")
    
    echo "├── 총 데이터: ${total_records}건"
    echo "├── 활성 코인: ${unique_coins}개"
    echo "└── 최근 1시간: ${recent_data}건"
}

show_service_urls() {
    print_info "🌐 서비스 접속 정보:"
    echo "├── Coin Q&A:        http://localhost:8080"
    echo "├── Market Summary:  ws://localhost:8765"
    echo "├── Dashboard:       http://localhost:8001"
    echo "├── TimescaleDB:     localhost:5432"
    if docker ps --format "table {{.Names}}" | grep -q "dashboard-react"; then
        echo "└── Next.js App:     http://localhost:3000"
    else
        echo "└── MCP Server:      localhost:9093"
    fi
}

# =============================================================================
# Individual Service Check
# =============================================================================

check_individual_service() {
    local service_name=$1
    
    if [ -z "$service_name" ]; then
        print_error "서비스 이름을 지정해주세요"
        echo "사용 가능한 서비스:"
        local services="timescaledb kafka zookeeper redis upbit-producer upbit-consumer mvp-coin-qa mvp-market-summary mvp-anomaly-detection dashboard-server mcp-server dashboard-react"
        for service in $services; do
            echo "  - $service"
        done
        return 1
    fi
    
    case $service_name in
        "timescaledb") check_timescaledb_health ;;
        "kafka") check_kafka_health ;;
        "zookeeper") check_zookeeper_health ;;
        "redis") check_redis_health ;;
        "upbit-producer") check_upbit_producer_health ;;
        "upbit-consumer") check_upbit_consumer_health ;;
        "mvp-coin-qa") check_coin_qa_health ;;
        "mvp-market-summary") check_market_summary_health ;;
        "mvp-anomaly-detection") check_anomaly_detection_health ;;
        "dashboard-server") check_dashboard_health ;;
        "mcp-server") check_mcp_server_health ;;
        "dashboard-react") check_nextjs_health ;;
        *) 
            print_error "알 수 없는 서비스: $service_name"
            return 1
            ;;
    esac
}

# =============================================================================
# Main Function
# =============================================================================

main() {
    setup_signal_handlers
    
    local action="${1:-full}"
    local service="${2:-}"
    
    case $action in
        "full" | "all")
            run_full_health_check
            ;;
        "infrastructure" | "infra")
            check_infrastructure_health
            ;;
        "pipeline" | "data")
            check_data_pipeline_health
            ;;
        "analytics" | "mvp")
            check_analytics_services_health
            ;;
        "optional")
            check_optional_services_health
            ;;
        "service")
            check_individual_service "$service"
            ;;
        "help" | "-h" | "--help")
            echo "사용법: $0 [옵션] [서비스명]"
            echo ""
            echo "옵션:"
            echo "  full, all              전체 상태 확인 (기본값)"
            echo "  infrastructure, infra  인프라 서비스만 확인"
            echo "  pipeline, data         데이터 파이프라인만 확인"
            echo "  analytics, mvp         분석 서비스만 확인"
            echo "  optional               선택적 서비스만 확인"
            echo "  service <name>         개별 서비스 확인"
            echo ""
            echo "개별 서비스 목록:"
            local services="timescaledb kafka zookeeper redis upbit-producer upbit-consumer mvp-coin-qa mvp-market-summary mvp-anomaly-detection dashboard-server mcp-server dashboard-react"
            for service in $services; do
                echo "  - $service"
            done
            ;;
        *)
            print_error "알 수 없는 옵션: $action"
            echo "도움말을 보려면: $0 help"
            exit 1
            ;;
    esac
}

# =============================================================================
# Script Execution
# =============================================================================

# 스크립트가 직접 실행되었을 때만 main 함수 실행
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi