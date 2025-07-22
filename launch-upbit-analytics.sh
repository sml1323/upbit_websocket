#!/bin/bash

# =============================================================================
# 🚀 Upbit Analytics Platform - Main Launcher Script
# =============================================================================
# Single command to launch the entire Upbit Analytics Platform
# Usage: ./launch-upbit-analytics.sh [--dev|--prod|--minimal|--full]
# =============================================================================

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source utility functions
source "$SCRIPT_DIR/scripts/utils.sh"

# =============================================================================
# Configuration Constants
# =============================================================================

readonly VERSION="1.0"
readonly DEFAULT_MODE="minimal"

# Service launch timeouts (seconds)
readonly INFRA_TIMEOUT=60
readonly PIPELINE_TIMEOUT=30
readonly ANALYTICS_TIMEOUT=45
readonly OPTIONAL_TIMEOUT=60

# Mode definitions - compatible with bash 3.2
get_mode_services() {
    case "$1" in
        "minimal") echo "timescaledb zookeeper kafka redis upbit-producer upbit-consumer mvp-coin-qa" ;;
        "dev") echo "timescaledb zookeeper kafka redis upbit-producer upbit-consumer mvp-coin-qa mvp-market-summary mvp-anomaly-detection dashboard-server" ;;
        "prod") echo "timescaledb zookeeper kafka redis upbit-producer upbit-consumer mvp-coin-qa mvp-market-summary mvp-anomaly-detection dashboard-server" ;;
        "full") echo "timescaledb zookeeper kafka redis upbit-producer upbit-consumer mvp-coin-qa mvp-market-summary mvp-anomaly-detection dashboard-server mcp-server dashboard-react" ;;
    esac
}

# Global variables
LAUNCH_MODE="$DEFAULT_MODE"
DRY_RUN=false
SKIP_VALIDATION=false
VERBOSE=false
INTERACTIVE_MODE=true

# =============================================================================
# Helper Functions
# =============================================================================

show_banner() {
    print_header "🚀 Upbit Analytics Platform Launcher v$VERSION"
    echo -e "${CYAN}===============================================${NC}"
    echo -e "${WHITE}모드: ${LAUNCH_MODE} | 예상 시간: ~$(get_estimated_time) | 포트: $(get_required_ports)${NC}"
    echo -e "${CYAN}===============================================${NC}"
    echo
}

get_estimated_time() {
    case $LAUNCH_MODE in
        "minimal") echo "2분" ;;
        "dev") echo "3분" ;;
        "prod") echo "3분" ;;
        "full") echo "4분" ;;
    esac
}

get_required_ports() {
    local ports="5432,9092,8080"
    
    case $LAUNCH_MODE in
        "dev"|"prod"|"full")
            ports="$ports,8765,8001"
            ;;
    esac
    
    if [[ "$LAUNCH_MODE" == "full" ]]; then
        ports="$ports,3000,9093"
    fi
    
    echo "$ports"
}

show_usage() {
    cat << EOF
🚀 Upbit Analytics Platform Launcher v$VERSION

사용법: $0 [옵션]

모드 옵션:
  --minimal     핵심 서비스만 실행 (DB + 데이터수집 + Q&A)
  --dev         개발 모드 (핵심 + 분석 서비스)
  --prod        운영 모드 (dev와 동일하지만 백그라운드 실행)
  --full        전체 모드 (모든 서비스 + MCP서버 + Next.js)

추가 옵션:
  --dry-run     실행 계획만 표시하고 종료
  --skip-validation  환경 검증 단계 건너뛰기
  --verbose     상세 로그 출력
  --quiet       비대화식 모드 (자동 진행)
  --help, -h    이 도움말 표시

예시:
  $0                    # minimal 모드로 실행
  $0 --full             # 전체 서비스 실행  
  $0 --dev --verbose    # 개발 모드, 상세 로그
  $0 --dry-run --full   # 전체 모드 실행 계획만 확인

서비스 정보:
  • TimescaleDB (5432) : 시계열 데이터베이스
  • Kafka (9092)       : 메시지 브로커
  • Redis (6379)       : 캐시 서버
  • Coin Q&A (8080)    : 코인 질의응답 API
  • Market Summary (8765) : 실시간 시장 요약
  • Dashboard (8001)   : 웹 대시보드
  • Next.js App (3000) : React 대시보드
  • MCP Server (9093)  : LLM 연동 서버
EOF
}

# =============================================================================
# Service Launch Functions
# =============================================================================

wait_for_service() {
    local service_name=$1
    local check_command=$2
    local timeout=${3:-30}
    local check_interval=${4:-2}
    
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        if eval "$check_command" >/dev/null 2>&1; then
            return 0
        fi
        
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
        show_progress $elapsed $timeout "$service_name 대기 중"
    done
    
    return 1
}

launch_infrastructure() {
    print_header "[1/5] 인프라 서비스 시작"
    
    local services=("timescaledb" "zookeeper" "kafka" "redis")
    local current=0
    local total=${#services[@]}
    
    for service in "${services[@]}"; do
        current=$((current + 1))
        
        local mode_services=$(get_mode_services "$LAUNCH_MODE")
        if [[ "$mode_services" =~ $service ]]; then
            print_progress "$service 시작 중..."
            
            if ! $DRY_RUN; then
                if start_docker_service "$service"; then
                    # 서비스별 헬스체크
                    case $service in
                        "timescaledb")
                            wait_for_service "TimescaleDB" "docker exec timescaledb pg_isready -U upbit_user -d upbit_analytics" 30
                            ;;
                        "kafka")
                            wait_for_service "Kafka" "docker exec kafka kafka-topics.sh --list --bootstrap-server localhost:9092" 30
                            ;;
                        "zookeeper")
                            wait_for_service "Zookeeper" "docker exec zookeeper nc -z localhost 2181" 15
                            ;;
                        "redis")
                            wait_for_service "Redis" "docker exec redis redis-cli ping | grep -q PONG" 15
                            ;;
                    esac
                    
                    if [ $? -eq 0 ]; then
                        show_progress $current $total "$service 완료"
                        print_success "$service 시작됨"
                    else
                        handle_error "$service" "헬스체크 실패"
                    fi
                else
                    handle_error "$service" "Docker 시작 실패"
                fi
            else
                print_info "[DRY-RUN] $service 시작 예정"
                show_progress $current $total "$service (시뮬레이션)"
            fi
        else
            print_info "$service 건너뜀 ($LAUNCH_MODE 모드에 포함되지 않음)"
        fi
        
        sleep 1
    done
    
    if ! $DRY_RUN; then
        print_progress "스키마 배포 확인 중..."
        if docker exec timescaledb psql -U upbit_user -d upbit_analytics -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='ticker_data';" -t | grep -q "1"; then
            print_success "TimescaleDB 스키마 확인됨"
        else
            print_warning "스키마를 배포해야 할 수 있습니다: python deploy_new_schema.py"
        fi
    fi
    
    echo
}

launch_data_pipeline() {
    print_header "[2/5] 데이터 파이프라인 구성"
    
    local services=("upbit-producer" "upbit-consumer")
    local current=0
    local total=${#services[@]}
    
    for service in "${services[@]}"; do
        current=$((current + 1))
        
        local mode_services=$(get_mode_services "$LAUNCH_MODE")
        if [[ "$mode_services" =~ $service ]]; then
            print_progress "$service 시작 중..."
            
            if ! $DRY_RUN; then
                if start_docker_service "$service"; then
                    # 데이터 파이프라인 헬스체크
                    case $service in
                        "upbit-producer")
                            sleep 5  # WebSocket 연결 대기
                            if docker logs upbit-producer --tail 5 2>/dev/null | grep -q -i "connected\|websocket"; then
                                print_success "Upbit Producer WebSocket 연결됨"
                            else
                                print_warning "Upbit Producer 연결 상태를 확인하세요"
                            fi
                            ;;
                        "upbit-consumer")
                            sleep 3  # Kafka 연결 대기
                            print_success "Data Consumer 시작됨"
                            ;;
                    esac
                    
                    show_progress $current $total "$service 완료"
                else
                    handle_error "$service" "시작 실패"
                fi
            else
                print_info "[DRY-RUN] $service 시작 예정"
                show_progress $current $total "$service (시뮬레이션)"
            fi
        fi
        
        sleep 2
    done
    
    if ! $DRY_RUN; then
        print_progress "첫 데이터 수신 대기 중..."
        sleep 10  # 첫 데이터 수집 대기
        
        local data_count=$(docker exec timescaledb psql -U upbit_user -d upbit_analytics -c "SELECT COUNT(*) FROM ticker_data WHERE timestamp > NOW() - INTERVAL '2 minutes';" -t 2>/dev/null | tr -d ' ')
        
        if [ -n "$data_count" ] && [ "$data_count" -gt 0 ]; then
            print_success "데이터 수신 확인됨 (${data_count}건)"
        else
            print_warning "아직 새 데이터가 수집되지 않았습니다"
        fi
    fi
    
    echo
}

launch_analytics_services() {
    print_header "[3/5] 분석 서비스 배포"
    
    local services=("mvp-coin-qa" "mvp-market-summary" "mvp-anomaly-detection" "dashboard-server")
    local current=0
    local total=0
    
    # 현재 모드에 포함된 서비스 수 계산
    for service in "${services[@]}"; do
        local mode_services=$(get_mode_services "$LAUNCH_MODE")
        if [[ "$mode_services" =~ $service ]]; then
            ((total++))
        fi
    done
    
    for service in "${services[@]}"; do
        local mode_services=$(get_mode_services "$LAUNCH_MODE")
        if [[ "$mode_services" =~ $service ]]; then
            current=$((current + 1))
            
            print_progress "$service 시작 중..."
            
            if ! $DRY_RUN; then
                if start_docker_service "$service"; then
                    # 서비스별 헬스체크
                    case $service in
                        "mvp-coin-qa")
                            wait_for_service "Coin Q&A" "curl -sf http://localhost:8080/health || netstat -tuln | grep -q :8080" 20
                            ;;
                        "mvp-market-summary")
                            wait_for_service "Market Summary" "netstat -tuln | grep -q :8765" 15
                            ;;
                        "mvp-anomaly-detection")
                            sleep 5  # 백그라운드 서비스 시작 대기
                            print_success "Anomaly Detection 백그라운드 실행 중"
                            ;;
                        "dashboard-server")
                            wait_for_service "Dashboard" "curl -sf http://localhost:8001 || netstat -tuln | grep -q :8001" 20
                            ;;
                    esac
                    
                    show_progress $current $total "$service 완료"
                    print_success "$service 시작됨"
                else
                    handle_error "$service" "시작 실패"
                fi
            else
                print_info "[DRY-RUN] $service 시작 예정"
                show_progress $current $total "$service (시뮬레이션)"
            fi
            
            sleep 2
        fi
    done
    
    echo
}

launch_optional_services() {
    if [[ "$LAUNCH_MODE" != "full" ]]; then
        return 0
    fi
    
    print_header "[4/5] 선택적 서비스 활성화"
    
    local services=("mcp-server" "dashboard-react")
    local current=0
    local total=${#services[@]}
    
    for service in "${services[@]}"; do
        current=$((current + 1))
        
        print_progress "$service 시작 중..."
        
        if ! $DRY_RUN; then
            if start_docker_service "$service"; then
                # 선택적 서비스 헬스체크
                case $service in
                    "mcp-server")
                        wait_for_service "MCP Server" "netstat -tuln | grep -q :9093" 30
                        ;;
                    "dashboard-react")
                        wait_for_service "Next.js Dashboard" "curl -sf http://localhost:3000" 45
                        ;;
                esac
                
                if [ $? -eq 0 ]; then
                    show_progress $current $total "$service 완료"
                    print_success "$service 시작됨"
                else
                    print_warning "$service 시작되었지만 헬스체크에 실패했습니다"
                fi
            else
                print_warning "$service 시작 실패 (선택적 서비스이므로 계속 진행)"
            fi
        else
            print_info "[DRY-RUN] $service 시작 예정"
            show_progress $current $total "$service (시뮬레이션)"
        fi
        
        sleep 3
    done
    
    echo
}

# =============================================================================
# Validation and Finalization
# =============================================================================

run_final_validation() {
    print_header "[5/5] 최종 검증 및 완료"
    
    if $DRY_RUN; then
        print_info "[DRY-RUN] 최종 검증 단계 시뮬레이션"
        return 0
    fi
    
    print_progress "서비스 상태 검증 중..."
    
    # 핵심 서비스만 검증 (빠른 검증)
    local critical_services=("timescaledb" "kafka" "mvp-coin-qa")
    local validation_passed=true
    
    for service in "${critical_services[@]}"; do
        local mode_services=$(get_mode_services "$LAUNCH_MODE")
        if [[ "$mode_services" =~ $service ]]; then
            case $service in
                "timescaledb")
                    if ! docker exec timescaledb pg_isready -U upbit_user -d upbit_analytics >/dev/null 2>&1; then
                        validation_passed=false
                        print_error "TimescaleDB 검증 실패"
                    fi
                    ;;
                "kafka")
                    if ! docker exec kafka kafka-topics.sh --list --bootstrap-server localhost:9092 >/dev/null 2>&1; then
                        validation_passed=false
                        print_error "Kafka 검증 실패"
                    fi
                    ;;
                "mvp-coin-qa")
                    if ! (curl -sf http://localhost:8080/health >/dev/null 2>&1 || netstat -tuln | grep -q ":8080"); then
                        validation_passed=false
                        print_error "Coin Q&A 검증 실패"
                    fi
                    ;;
            esac
        fi
    done
    
    if $validation_passed; then
        print_success "핵심 서비스 검증 완료"
    else
        print_warning "일부 서비스 검증에 실패했습니다"
    fi
}

show_completion_summary() {
    local end_time=$(date +%s)
    local duration=$((end_time - SCRIPT_START_TIME))
    
    echo
    print_header "✅ Upbit Analytics Platform 실행 완료!"
    
    if $DRY_RUN; then
        print_info "DRY-RUN 모드로 실행 계획을 확인했습니다"
        return 0
    fi
    
    echo -e "${GREEN}실행 시간: $(format_duration $duration)${NC}"
    echo
    
    # 서비스 접속 정보
    print_info "🌐 서비스 접속 정보:"
    
    local services_shown=false
    
    local mode_services=$(get_mode_services "$LAUNCH_MODE")
    
    if [[ "$mode_services" =~ "mvp-coin-qa" ]]; then
        echo "├── ${EMOJI_ROBOT} Coin Q&A:        http://localhost:8080"
        services_shown=true
    fi
    
    if [[ "$mode_services" =~ "mvp-market-summary" ]]; then
        echo "├── ${EMOJI_CHART} Market Summary:  ws://localhost:8765"
        services_shown=true
    fi
    
    if [[ "$mode_services" =~ "dashboard-server" ]]; then
        echo "├── ${EMOJI_DASHBOARD} Dashboard:       http://localhost:8001"
        services_shown=true
    fi
    
    if [[ "$mode_services" =~ "dashboard-react" ]]; then
        echo "├── ${EMOJI_REACT} Next.js App:     http://localhost:3000"
        services_shown=true
    fi
    
    if [[ "$mode_services" =~ "mcp-server" ]]; then
        echo "├── ${EMOJI_LINK} MCP Server:      localhost:9093"
        services_shown=true
    fi
    
    echo "└── ${EMOJI_DATABASE} TimescaleDB:     localhost:5432"
    
    echo
    
    # 데이터 현황 (간단히)
    local total_records=$(docker exec timescaledb psql -U upbit_user -d upbit_analytics -c "SELECT COUNT(*) FROM ticker_data;" -t 2>/dev/null | tr -d ' ' || echo "확인불가")
    local unique_coins=$(docker exec timescaledb psql -U upbit_user -d upbit_analytics -c "SELECT COUNT(DISTINCT market) FROM ticker_data;" -t 2>/dev/null | tr -d ' ' || echo "확인불가")
    
    print_info "📊 현재 데이터 현황:"
    echo "├── 총 데이터: ${total_records}건"
    echo "└── 활성 코인: ${unique_coins}개"
    
    echo
    
    # 유용한 명령어
    print_info "⌨️  유용한 명령어:"
    echo "├── 전체 상태 확인:  ./scripts/health-check.sh"
    echo "├── 서비스 로그:     ./scripts/logs.sh [service-name]"
    echo "└── 시스템 종료:     ./scripts/stop-all.sh"
    
    echo
    print_success "${EMOJI_SUCCESS} 모든 서비스가 성공적으로 실행되었습니다!"
}

# =============================================================================
# Main Execution Function
# =============================================================================

run_dry_run() {
    show_banner
    
    echo -e "${YELLOW}${EMOJI_INFO} DRY-RUN 모드 - 실제 실행 없이 계획만 표시합니다${NC}"
    echo
    
    print_info "실행될 서비스 목록:"
    local mode_services=$(get_mode_services "$LAUNCH_MODE")
    for service in $mode_services; do
        echo "  • $service"
    done
    
    echo
    print_info "실행 단계:"
    echo "  [1/5] 인프라 서비스 시작 (TimescaleDB, Kafka, Redis 등)"
    echo "  [2/5] 데이터 파이프라인 구성 (Producer, Consumer)"
    echo "  [3/5] 분석 서비스 배포 (Q&A, Summary, Dashboard 등)"
    
    if [[ "$LAUNCH_MODE" == "full" ]]; then
        echo "  [4/5] 선택적 서비스 활성화 (MCP Server, Next.js)"
    fi
    
    echo "  [5/5] 최종 검증 및 완료"
    
    echo
    print_info "예상 실행 시간: $(get_estimated_time)"
    print_info "사용할 포트: $(get_required_ports)"
    
    echo
    print_success "DRY-RUN 완료. 실제 실행하려면 --dry-run 옵션 없이 다시 실행하세요."
}

main() {
    setup_signal_handlers
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --minimal)
                LAUNCH_MODE="minimal"
                shift
                ;;
            --dev)
                LAUNCH_MODE="dev"
                shift
                ;;
            --prod)
                LAUNCH_MODE="prod"
                INTERACTIVE_MODE=false
                shift
                ;;
            --full)
                LAUNCH_MODE="full"
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --skip-validation)
                SKIP_VALIDATION=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                CURRENT_LOG_LEVEL=$LOG_DEBUG
                shift
                ;;
            --quiet)
                INTERACTIVE_MODE=false
                shift
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
    
    # DRY-RUN 모드 처리
    if $DRY_RUN; then
        run_dry_run
        exit 0
    fi
    
    # 실제 실행
    show_banner
    
    # Phase 0: Environment Validation (if not skipped)
    if ! $SKIP_VALIDATION; then
        print_header "[0/5] 환경 검증"
        
        if validate_environment; then
            print_success "환경 검증 완료"
        else
            if $INTERACTIVE_MODE; then
                if ! confirm_action "환경 검증에 일부 실패했습니다. 계속 진행하시겠습니까?"; then
                    cleanup_and_exit 1
                fi
            else
                print_warning "환경 검증에 실패했지만 계속 진행합니다"
            fi
        fi
        echo
    fi
    
    # Execute phases
    launch_infrastructure
    launch_data_pipeline  
    launch_analytics_services
    launch_optional_services
    run_final_validation
    
    # Show completion summary
    show_completion_summary
}

# =============================================================================
# Script Entry Point
# =============================================================================

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi