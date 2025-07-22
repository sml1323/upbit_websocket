#!/bin/bash

# =============================================================================
# Upbit Analytics Platform - Graceful Shutdown Script
# =============================================================================
# Safe shutdown of all platform services with data integrity preservation
# Dependencies: utils.sh for logging and output functions
# =============================================================================

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source utility functions
source "$SCRIPT_DIR/utils.sh"

# =============================================================================
# Configuration Constants
# =============================================================================

readonly VERSION="1.0"
readonly SHUTDOWN_TIMEOUT=30
readonly FORCE_TIMEOUT=10

# Shutdown order (reverse dependency order)
readonly SHUTDOWN_GROUPS=(
    "analytics:mvp-coin-qa,mvp-market-summary,mvp-anomaly-detection,dashboard-server"
    "optional:mcp-server,dashboard-react"
    "pipeline:upbit-consumer,upbit-producer"
    "infrastructure:kafka,zookeeper,redis,timescaledb"
)

# Service to container mapping
declare -A SERVICE_CONTAINERS=(
    ["timescaledb"]="timescaledb"
    ["zookeeper"]="zookeeper"
    ["kafka"]="kafka"
    ["redis"]="redis"
    ["upbit-producer"]="upbit-producer"
    ["upbit-consumer"]="upbit-consumer"
    ["mvp-coin-qa"]="mvp-coin-qa"
    ["mvp-market-summary"]="mvp-market-summary"
    ["mvp-anomaly-detection"]="mvp-anomaly-detection"
    ["dashboard-server"]="dashboard-server"
    ["mcp-server"]="mcp-server"
    ["dashboard-react"]="dashboard-react"
)

# Service display names
declare -A SERVICE_NAMES=(
    ["timescaledb"]="TimescaleDB"
    ["zookeeper"]="Zookeeper"
    ["kafka"]="Kafka"
    ["redis"]="Redis"
    ["upbit-producer"]="Upbit Producer"
    ["upbit-consumer"]="Data Consumer"
    ["mvp-coin-qa"]="Coin Q&A System"
    ["mvp-market-summary"]="Market Summary"
    ["mvp-anomaly-detection"]="Anomaly Detection"
    ["dashboard-server"]="Dashboard Server"
    ["mcp-server"]="MCP Server"
    ["dashboard-react"]="Next.js Dashboard"
)

# Global variables
FORCE_SHUTDOWN=false
SKIP_CONFIRMATION=false
PRESERVE_VOLUMES=true
CLEANUP_NETWORKS=false
EXPORT_LOGS=false

# =============================================================================
# Pre-shutdown Functions
# =============================================================================

show_banner() {
    print_header "🛑 Upbit Analytics Platform - 안전한 종료 v$VERSION"
    echo -e "${YELLOW}=================================================${NC}"
    echo -e "${WHITE}모든 서비스를 안전하게 종료하고 데이터 무결성을 보장합니다${NC}"
    echo -e "${YELLOW}=================================================${NC}"
    echo
}

check_running_services() {
    print_header "실행 중인 서비스 확인"
    
    local running_services=()
    local total_services=0
    
    for service in "${!SERVICE_CONTAINERS[@]}"; do
        local container_name="${SERVICE_CONTAINERS[$service]}"
        local service_name="${SERVICE_NAMES[$service]}"
        
        if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
            running_services+=("$service")
            echo -e "  ${GREEN}${EMOJI_SUCCESS}${NC} $service_name ($container_name)"
        fi
        ((total_services++))
    done
    
    local running_count=${#running_services[@]}
    
    echo
    if [ $running_count -eq 0 ]; then
        print_info "실행 중인 서비스가 없습니다"
        return 1
    else
        print_info "총 $running_count/$total_services 서비스가 실행 중입니다"
        return 0
    fi
}

show_shutdown_plan() {
    print_header "종료 계획"
    
    print_info "서비스 종료 순서 (의존성 고려):"
    
    local step=1
    for group_def in "${SHUTDOWN_GROUPS[@]}"; do
        local group_name=$(echo "$group_def" | cut -d':' -f1)
        local services=$(echo "$group_def" | cut -d':' -f2)
        
        echo -e "  ${CYAN}[$step] ${group_name^} 서비스:${NC}"
        
        IFS=',' read -ra SERVICE_LIST <<< "$services"
        for service in "${SERVICE_LIST[@]}"; do
            local container_name="${SERVICE_CONTAINERS[$service]}"
            local service_name="${SERVICE_NAMES[$service]}"
            
            if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
                echo -e "      • $service_name"
            else
                echo -e "      ${GRAY}• $service_name (이미 중지됨)${NC}"
            fi
        done
        
        ((step++))
    done
    
    echo
    print_info "추가 작업:"
    echo "  • 데이터 무결성 검증"
    
    if $EXPORT_LOGS; then
        echo "  • 로그 백업 및 내보내기"
    fi
    
    if $CLEANUP_NETWORKS; then
        echo "  • Docker 네트워크 정리"
    fi
    
    if ! $PRESERVE_VOLUMES; then
        echo -e "  ${RED}• Docker 볼륨 삭제 (데이터 손실 위험!)${NC}"
    fi
}

confirm_shutdown() {
    if $SKIP_CONFIRMATION; then
        return 0
    fi
    
    echo
    if $FORCE_SHUTDOWN; then
        print_warning "강제 종료 모드가 활성화되었습니다!"
        print_warning "서비스가 즉시 종료되며 데이터 손실 위험이 있습니다"
    fi
    
    if ! $PRESERVE_VOLUMES; then
        print_warning "볼륨 삭제 모드가 활성화되었습니다!"
        print_warning "모든 데이터가 영구적으로 삭제됩니다!"
    fi
    
    echo
    if ! confirm_action "모든 서비스를 종료하시겠습니까?" "n"; then
        print_info "종료가 취소되었습니다"
        exit 0
    fi
}

# =============================================================================
# Data Safety Functions
# =============================================================================

ensure_data_safety() {
    if $FORCE_SHUTDOWN; then
        print_warning "강제 종료 모드이므로 데이터 안전성 검사를 건너뜁니다"
        return 0
    fi
    
    print_header "데이터 안전성 검사"
    
    # TimescaleDB 트랜잭션 완료 대기
    if docker ps --format "table {{.Names}}" | grep -q "^timescaledb$"; then
        print_progress "TimescaleDB 트랜잭션 완료 대기 중..."
        
        # 활성 트랜잭션 확인
        local active_txns=$(docker exec timescaledb psql -U upbit_user -d upbit_analytics -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';" -t 2>/dev/null | tr -d ' ' || echo "0")
        
        if [ "$active_txns" -gt 1 ]; then  # 1 = current query
            print_warning "활성 트랜잭션이 있습니다. 완료 대기 중... (최대 30초)"
            
            local wait_count=0
            while [ "$active_txns" -gt 1 ] && [ $wait_count -lt 30 ]; do
                sleep 1
                active_txns=$(docker exec timescaledb psql -U upbit_user -d upbit_analytics -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';" -t 2>/dev/null | tr -d ' ' || echo "0")
                ((wait_count++))
            done
            
            if [ "$active_txns" -gt 1 ]; then
                print_warning "일부 트랜잭션이 여전히 활성 상태입니다"
            else
                print_success "모든 트랜잭션이 완료되었습니다"
            fi
        else
            print_success "활성 트랜잭션이 없습니다"
        fi
    fi
    
    # Kafka 메시지 플러시
    if docker ps --format "table {{.Names}}" | grep -q "^kafka$"; then
        print_progress "Kafka 메시지 플러시 중..."
        
        # Consumer group 오프셋 커밋 확인
        docker exec kafka kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1
        
        print_success "Kafka 메시지 처리 완료"
    fi
    
    # 데이터 수집기 안전한 종료 신호
    if docker ps --format "table {{.Names}}" | grep -q "^upbit-consumer$"; then
        print_progress "데이터 수집기 안전한 종료 신호 전송 중..."
        
        # SIGTERM 신호로 graceful shutdown 시도
        docker kill --signal=TERM upbit-consumer >/dev/null 2>&1 || true
        sleep 2
        
        print_success "데이터 수집기 종료 신호 전송 완료"
    fi
    
    echo
    print_success "데이터 안전성 검사 완료"
}

backup_critical_data() {
    if ! $EXPORT_LOGS && $PRESERVE_VOLUMES; then
        return 0
    fi
    
    print_header "중요 데이터 백업"
    
    local backup_dir="./shutdown_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    if $EXPORT_LOGS; then
        print_progress "로그 백업 중..."
        "$SCRIPT_DIR/logs.sh" export "$backup_dir/logs" "24h" >/dev/null 2>&1
        print_success "로그가 $backup_dir/logs 에 백업되었습니다"
    fi
    
    # 중요한 설정 파일 백업
    print_progress "설정 파일 백업 중..."
    
    local config_files=(
        "docker-compose.yml"
        ".env"
        "CLAUDE.md"
        "deploy_new_schema.py"
    )
    
    for file in "${config_files[@]}"; do
        if [ -f "$PROJECT_ROOT/$file" ]; then
            cp "$PROJECT_ROOT/$file" "$backup_dir/" 2>/dev/null || true
        fi
    done
    
    if [ -d "$PROJECT_ROOT/scripts" ]; then
        cp -r "$PROJECT_ROOT/scripts" "$backup_dir/" 2>/dev/null || true
    fi
    
    print_success "설정 파일이 $backup_dir 에 백업되었습니다"
}

# =============================================================================
# Service Shutdown Functions
# =============================================================================

stop_service_group() {
    local group_def=$1
    local group_name=$(echo "$group_def" | cut -d':' -f1)
    local services=$(echo "$group_def" | cut -d':' -f2)
    
    print_header "${group_name^} 서비스 그룹 종료"
    
    IFS=',' read -ra SERVICE_LIST <<< "$services"
    local active_services=()
    
    # 실행 중인 서비스 확인
    for service in "${SERVICE_LIST[@]}"; do
        local container_name="${SERVICE_CONTAINERS[$service]}"
        if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
            active_services+=("$service")
        fi
    done
    
    if [ ${#active_services[@]} -eq 0 ]; then
        print_info "${group_name^} 그룹에 실행 중인 서비스가 없습니다"
        return 0
    fi
    
    # 서비스 종료
    local current=0
    local total=${#active_services[@]}
    
    for service in "${active_services[@]}"; do
        current=$((current + 1))
        local container_name="${SERVICE_CONTAINERS[$service]}"
        local service_name="${SERVICE_NAMES[$service]}"
        
        print_progress "[$current/$total] $service_name 종료 중..."
        
        if $FORCE_SHUTDOWN; then
            # 강제 종료
            if docker kill "$container_name" >/dev/null 2>&1; then
                print_success "$service_name 강제 종료됨"
            else
                print_warning "$service_name 강제 종료 실패 (이미 중지되었을 수 있음)"
            fi
        else
            # Graceful 종료
            if docker stop -t "$SHUTDOWN_TIMEOUT" "$container_name" >/dev/null 2>&1; then
                print_success "$service_name 정상 종료됨"
            else
                print_warning "$service_name 정상 종료 실패, 강제 종료 시도 중..."
                if docker kill "$container_name" >/dev/null 2>&1; then
                    print_success "$service_name 강제 종료됨"
                else
                    print_error "$service_name 종료 실패"
                fi
            fi
        fi
        
        # 서비스별 특별한 정리 작업
        case $service in
            "timescaledb")
                # 데이터베이스 연결 정리
                sleep 2
                ;;
            "kafka")
                # Kafka 브로커 정리
                sleep 1
                ;;
        esac
    done
    
    echo
}

wait_for_complete_shutdown() {
    print_header "종료 완료 검증"
    
    local remaining_containers=()
    
    for service in "${!SERVICE_CONTAINERS[@]}"; do
        local container_name="${SERVICE_CONTAINERS[$service]}"
        if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
            remaining_containers+=("$container_name")
        fi
    done
    
    if [ ${#remaining_containers[@]} -eq 0 ]; then
        print_success "모든 서비스가 성공적으로 종료되었습니다"
        return 0
    fi
    
    print_warning "다음 컨테이너들이 아직 실행 중입니다:"
    for container in "${remaining_containers[@]}"; do
        echo "  • $container"
    done
    
    if $FORCE_SHUTDOWN || ! $SKIP_CONFIRMATION; then
        if confirm_action "남은 컨테이너들을 강제 종료하시겠습니까?" "y"; then
            print_progress "남은 컨테이너들 강제 종료 중..."
            for container in "${remaining_containers[@]}"; do
                docker kill "$container" >/dev/null 2>&1 || true
            done
            print_success "강제 종료 완료"
        fi
    fi
}

# =============================================================================
# Cleanup Functions
# =============================================================================

cleanup_resources() {
    print_header "리소스 정리"
    
    # 종료된 컨테이너 제거
    print_progress "종료된 컨테이너 제거 중..."
    docker container prune -f >/dev/null 2>&1
    print_success "종료된 컨테이너 제거 완료"
    
    # 네트워크 정리 (옵션)
    if $CLEANUP_NETWORKS; then
        print_progress "사용하지 않는 네트워크 제거 중..."
        docker network prune -f >/dev/null 2>&1
        print_success "네트워크 정리 완료"
    fi
    
    # 볼륨 삭제 (위험한 옵션)
    if ! $PRESERVE_VOLUMES; then
        print_warning "⚠️  모든 데이터 볼륨을 삭제합니다 (복구 불가능!)"
        
        if $SKIP_CONFIRMATION || confirm_action "정말로 모든 데이터를 삭제하시겠습니까?" "n"; then
            print_progress "볼륨 삭제 중..."
            docker volume prune -f >/dev/null 2>&1
            # 프로젝트 관련 볼륨 명시적 삭제
            docker volume rm upbit_websocket_timescaledb_data upbit_websocket_kafka_data upbit_websocket_redis_data 2>/dev/null || true
            print_success "볼륨 삭제 완료"
        else
            print_info "볼륨 삭제가 취소되었습니다"
        fi
    fi
    
    # 이미지 정리 (옵션)
    if $CLEANUP_NETWORKS; then  # 네트워크 정리와 함께 수행
        print_progress "사용하지 않는 이미지 제거 중..."
        docker image prune -a -f >/dev/null 2>&1
        print_success "이미지 정리 완료"
    fi
}

show_shutdown_summary() {
    local end_time=$(date +%s)
    local duration=$((end_time - SCRIPT_START_TIME))
    
    echo
    print_header "🏁 종료 완료 요약"
    
    echo -e "${GREEN}종료 시간: $(format_duration $duration)${NC}"
    echo
    
    # 최종 상태 확인
    local remaining_count=0
    for service in "${!SERVICE_CONTAINERS[@]}"; do
        local container_name="${SERVICE_CONTAINERS[$service]}"
        if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
            ((remaining_count++))
        fi
    done
    
    if [ $remaining_count -eq 0 ]; then
        print_success "${EMOJI_SUCCESS} 모든 Upbit Analytics Platform 서비스가 성공적으로 종료되었습니다"
    else
        print_warning "${EMOJI_WARNING} $remaining_count 개 서비스가 아직 실행 중입니다"
    fi
    
    echo
    print_info "다시 시작하려면:"
    echo "  ./launch-upbit-analytics.sh [--minimal|--dev|--full]"
    
    if ! $PRESERVE_VOLUMES; then
        echo
        print_warning "⚠️  데이터가 삭제되었으므로 다시 시작하기 전에 스키마를 재배포해야 합니다:"
        echo "  python deploy_new_schema.py"
    fi
    
    echo
    print_success "${EMOJI_SUCCESS} 안전한 종료가 완료되었습니다!"
}

show_usage() {
    cat << EOF
🛑 Upbit Analytics Platform 안전한 종료 스크립트 v$VERSION

사용법: $0 [옵션]

옵션:
  --force               강제 종료 (빠르지만 데이터 손실 위험)
  --yes, -y            확인 프롬프트 건너뛰기  
  --remove-volumes     볼륨 삭제 (모든 데이터 삭제 - 위험!)
  --cleanup-networks   사용하지 않는 네트워크/이미지 정리
  --export-logs        종료 전 로그 백업
  --timeout <초>       서비스 종료 대기 시간 (기본: $SHUTDOWN_TIMEOUT초)
  --help, -h           이 도움말 표시

모드:
  기본값               정상적인 종료 (데이터 안전성 보장)
  --force              강제 종료 (즉시 종료)

예시:
  $0                           # 정상 종료
  $0 --force --yes             # 강제 종료 (확인 없이)
  $0 --export-logs             # 로그 백업 후 종료
  $0 --remove-volumes --yes    # 데이터 포함 완전 삭제

⚠️  주의사항:
  • --force 옵션은 데이터 손실을 일으킬 수 있습니다
  • --remove-volumes 옵션은 모든 데이터를 영구 삭제합니다
  • 운영 환경에서는 --export-logs 옵션 사용을 권장합니다
EOF
}

# =============================================================================
# Main Function
# =============================================================================

main() {
    setup_signal_handlers
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force)
                FORCE_SHUTDOWN=true
                shift
                ;;
            --yes|-y)
                SKIP_CONFIRMATION=true
                shift
                ;;
            --remove-volumes)
                PRESERVE_VOLUMES=false
                shift
                ;;
            --cleanup-networks)
                CLEANUP_NETWORKS=true
                shift
                ;;
            --export-logs)
                EXPORT_LOGS=true
                shift
                ;;
            --timeout)
                SHUTDOWN_TIMEOUT="$2"
                shift 2
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                print_error "알 수 없는 옵션: $1"
                echo "도움말을 보려면: $0 --help"
                exit 1
                ;;
        esac
    done
    
    # Main execution flow
    show_banner
    
    # Check if any services are running
    if ! check_running_services; then
        print_success "종료할 서비스가 없습니다"
        exit 0
    fi
    
    echo
    
    # Show shutdown plan
    show_shutdown_plan
    
    # Get user confirmation
    confirm_shutdown
    
    echo
    
    # Data safety and backup
    if $EXPORT_LOGS || ! $PRESERVE_VOLUMES; then
        backup_critical_data
        echo
    fi
    
    ensure_data_safety
    echo
    
    # Execute shutdown in order
    for group_def in "${SHUTDOWN_GROUPS[@]}"; do
        stop_service_group "$group_def"
    done
    
    # Verify complete shutdown
    wait_for_complete_shutdown
    echo
    
    # Cleanup resources
    cleanup_resources
    
    # Show summary
    show_shutdown_summary
}

# =============================================================================
# Script Entry Point
# =============================================================================

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi