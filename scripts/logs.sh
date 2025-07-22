#!/bin/bash

# =============================================================================
# Upbit Analytics Platform - Log Management System
# =============================================================================
# Unified log viewing and management for all platform services
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

readonly LOG_LINES_DEFAULT=50
readonly LOG_FOLLOW_DEFAULT=false
readonly LOG_TIMESTAMP_DEFAULT=true

# Service to container mapping - bash 3.2 compatible
get_service_container() {
    case "$1" in
        "timescaledb") echo "timescaledb" ;;
        "zookeeper") echo "zookeeper" ;;
        "kafka") echo "kafka" ;;
        "redis") echo "redis" ;;
        "upbit-producer") echo "upbit-producer" ;;
        "upbit-consumer") echo "upbit-consumer" ;;
        "mvp-coin-qa") echo "mvp-coin-qa" ;;
        "mvp-market-summary") echo "mvp-market-summary" ;;
        "mvp-anomaly-detection") echo "mvp-anomaly-detection" ;;
        "dashboard-server") echo "dashboard-server" ;;
        "mcp-server") echo "mcp-server" ;;
        "dashboard-react") echo "dashboard-react" ;;
    esac
}

# Service display names
get_service_name() {
    case "$1" in
        "timescaledb") echo "TimescaleDB" ;;
        "zookeeper") echo "Zookeeper" ;;
        "kafka") echo "Kafka" ;;
        "redis") echo "Redis" ;;
        "upbit-producer") echo "Upbit Producer" ;;
        "upbit-consumer") echo "Data Consumer" ;;
        "mvp-coin-qa") echo "Coin Q&A System" ;;
        "mvp-market-summary") echo "Market Summary" ;;
        "mvp-anomaly-detection") echo "Anomaly Detection" ;;
        "dashboard-server") echo "Dashboard Server" ;;
        "mcp-server") echo "MCP Server" ;;
        "dashboard-react") echo "Next.js Dashboard" ;;
    esac
}

# =============================================================================
# Log Viewing Functions
# =============================================================================

show_individual_logs() {
    local service=$1
    local lines=${2:-$LOG_LINES_DEFAULT}
    local follow=${3:-$LOG_FOLLOW_DEFAULT}
    local since=${4:-""}
    
    if [ -z "$service" ]; then
        print_error "서비스 이름을 지정해주세요"
        show_available_services
        return 1
    fi
    
    local container_name=$(get_service_container "$service")
    local service_name=$(get_service_name "$service")
    
    if [ -z "$container_name" ]; then
        print_error "알 수 없는 서비스: $service"
        show_available_services
        return 1
    fi
    
    # 컨테이너 실행 상태 확인
    if ! docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
        print_error "$service_name 컨테이너가 실행 중이지 않습니다"
        return 1
    fi
    
    print_header "$service_name 로그 보기"
    
    # Docker logs 명령 구성
    local docker_cmd="docker logs"
    
    if $follow; then
        docker_cmd="$docker_cmd -f"
    fi
    
    if [ -n "$since" ]; then
        docker_cmd="$docker_cmd --since=$since"
    fi
    
    docker_cmd="$docker_cmd --tail=$lines"
    
    if $LOG_TIMESTAMP_DEFAULT; then
        docker_cmd="$docker_cmd -t"
    fi
    
    docker_cmd="$docker_cmd $container_name"
    
    print_info "실행 중: $docker_cmd"
    
    if $follow; then
        print_info "실시간 로그 추적 중... (종료하려면 Ctrl+C를 누르세요)"
        echo
    fi
    
    # 로그 실행
    eval $docker_cmd
}

show_aggregated_logs() {
    local lines=${1:-$LOG_LINES_DEFAULT}
    local since=${2:-"1h"}
    
    print_header "전체 서비스 통합 로그 보기"
    
    local running_services=()
    
    # 실행 중인 서비스 찾기
    for service in "${!SERVICE_CONTAINERS[@]}"; do
        local container_name="${SERVICE_CONTAINERS[$service]}"
        if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
            running_services+=("$service")
        fi
    done
    
    if [ ${#running_services[@]} -eq 0 ]; then
        print_warning "실행 중인 서비스가 없습니다"
        return 1
    fi
    
    print_info "실행 중인 서비스: ${running_services[*]}"
    echo
    
    # 각 서비스의 최근 로그를 시간순으로 표시
    local temp_dir=$(mktemp -d)
    
    for service in "${running_services[@]}"; do
        local container_name="${SERVICE_CONTAINERS[$service]}"
        local service_name="${SERVICE_NAMES[$service]}"
        
        print_progress "$service_name 로그 수집 중..."
        
        # 로그를 임시 파일에 저장 (타임스탬프와 서비스명 포함)
        docker logs --since="$since" --tail="$lines" -t "$container_name" 2>&1 | \
        sed "s/^/[$service_name] /" > "$temp_dir/$service.log"
    done
    
    print_success "로그 수집 완료, 시간순 정렬 중..."
    echo
    
    # 모든 로그 파일을 합치고 시간순 정렬
    cat "$temp_dir"/*.log | sort -k1,1 | tail -n "$lines"
    
    # 임시 디렉토리 정리
    rm -rf "$temp_dir"
}

show_error_logs() {
    local lines=${1:-100}
    local since=${2:-"1h"}
    
    print_header "에러 로그 분석"
    
    local running_services=()
    
    # 실행 중인 서비스 찾기
    for service in "${!SERVICE_CONTAINERS[@]}"; do
        local container_name="${SERVICE_CONTAINERS[$service]}"
        if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
            running_services+=("$service")
        fi
    done
    
    if [ ${#running_services[@]} -eq 0 ]; then
        print_warning "실행 중인 서비스가 없습니다"
        return 1
    fi
    
    local errors_found=false
    
    for service in "${running_services[@]}"; do
        local container_name="${SERVICE_CONTAINERS[$service]}"
        local service_name="${SERVICE_NAMES[$service]}"
        
        print_progress "$service_name 에러 로그 검색 중..."
        
        # 에러 키워드로 로그 필터링
        local error_patterns="ERROR|FATAL|CRITICAL|Exception|Error|Failed|failed|FAILED"
        local error_logs=$(docker logs --since="$since" --tail="$lines" "$container_name" 2>&1 | \
                          grep -E "$error_patterns" || true)
        
        if [ -n "$error_logs" ]; then
            errors_found=true
            echo
            print_warning "${EMOJI_ERROR} $service_name 에러 발견:"
            echo -e "${RED}$error_logs${NC}"
        fi
    done
    
    if ! $errors_found; then
        echo
        print_success "최근 ${since} 동안 심각한 에러가 발견되지 않았습니다"
    fi
}

show_performance_logs() {
    local lines=${1:-50}
    local since=${2:-"30m"}
    
    print_header "성능 관련 로그 분석"
    
    local performance_services=("upbit-producer" "upbit-consumer" "mvp-coin-qa" "timescaledb")
    
    for service in "${performance_services[@]}"; do
        local container_name="${SERVICE_CONTAINERS[$service]}"
        local service_name="${SERVICE_NAMES[$service]}"
        
        if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
            print_progress "$service_name 성능 로그 검색 중..."
            
            # 성능 관련 키워드 검색
            local perf_patterns="slow|timeout|memory|cpu|connection|latency|ms|seconds"
            local perf_logs=$(docker logs --since="$since" --tail="$lines" "$container_name" 2>&1 | \
                             grep -i -E "$perf_patterns" | head -10 || true)
            
            if [ -n "$perf_logs" ]; then
                echo
                print_info "${EMOJI_ANALYTICS} $service_name 성능 관련 로그:"
                echo -e "${CYAN}$perf_logs${NC}"
            fi
        fi
    done
}

# =============================================================================
# Interactive Log Explorer
# =============================================================================

start_interactive_explorer() {
    print_header "🔍 대화형 로그 탐색기"
    
    while true; do
        echo
        print_info "옵션을 선택하세요:"
        echo "  1) 개별 서비스 로그 보기"
        echo "  2) 전체 서비스 통합 로그"
        echo "  3) 에러 로그만 보기"
        echo "  4) 성능 관련 로그 보기"
        echo "  5) 실시간 로그 추적"
        echo "  6) 서비스 상태 확인"
        echo "  0) 종료"
        
        echo -n "선택 (0-6): "
        read -r choice
        
        case $choice in
            1)
                echo
                show_available_services
                echo -n "서비스 이름 입력: "
                read -r service_name
                echo -n "라인 수 (기본: $LOG_LINES_DEFAULT): "
                read -r line_count
                line_count=${line_count:-$LOG_LINES_DEFAULT}
                show_individual_logs "$service_name" "$line_count"
                ;;
            2)
                echo -n "라인 수 (기본: $LOG_LINES_DEFAULT): "
                read -r line_count
                line_count=${line_count:-$LOG_LINES_DEFAULT}
                echo -n "시간 범위 (기본: 1h): "
                read -r time_range
                time_range=${time_range:-1h}
                show_aggregated_logs "$line_count" "$time_range"
                ;;
            3)
                echo -n "라인 수 (기본: 100): "
                read -r line_count
                line_count=${line_count:-100}
                show_error_logs "$line_count"
                ;;
            4)
                show_performance_logs
                ;;
            5)
                echo
                show_available_services
                echo -n "실시간 추적할 서비스 이름: "
                read -r service_name
                show_individual_logs "$service_name" "$LOG_LINES_DEFAULT" true
                ;;
            6)
                "$SCRIPT_DIR/health-check.sh"
                ;;
            0)
                print_info "로그 탐색기를 종료합니다"
                break
                ;;
            *)
                print_error "잘못된 선택입니다"
                ;;
        esac
        
        if [ "$choice" != "0" ]; then
            echo
            echo -n "계속하려면 Enter를 누르세요..."
            read -r
        fi
    done
}

# =============================================================================
# Log Management Functions
# =============================================================================

rotate_logs() {
    print_header "로그 회전 및 정리"
    
    print_info "Docker 로그 정리 중..."
    
    # Docker 로그 정리 (7일 이상 된 로그 삭제)
    docker system prune --volumes -f >/dev/null 2>&1
    
    # 각 컨테이너의 로그 크기 확인
    print_info "컨테이너별 로그 크기:"
    
    for service in "${!SERVICE_CONTAINERS[@]}"; do
        local container_name="${SERVICE_CONTAINERS[$service]}"
        local service_name="${SERVICE_NAMES[$service]}"
        
        if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
            local log_size=$(docker logs "$container_name" 2>&1 | wc -c | numfmt --to=iec)
            echo "  $service_name: $log_size"
        fi
    done
    
    print_success "로그 정리 완료"
}

export_logs() {
    local output_dir="${1:-./logs_export_$(date +%Y%m%d_%H%M%S)}"
    local since="${2:-1h}"
    
    print_header "로그 내보내기"
    
    mkdir -p "$output_dir"
    
    print_info "로그를 $output_dir 디렉토리로 내보냅니다..."
    
    local exported_count=0
    
    for service in "${!SERVICE_CONTAINERS[@]}"; do
        local container_name="${SERVICE_CONTAINERS[$service]}"
        local service_name="${SERVICE_NAMES[$service]}"
        
        if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
            print_progress "$service_name 로그 내보내는 중..."
            
            local log_file="$output_dir/${service}.log"
            docker logs --since="$since" -t "$container_name" > "$log_file" 2>&1
            
            if [ -s "$log_file" ]; then
                ((exported_count++))
                print_success "$service_name 로그 내보냄: $log_file"
            else
                rm "$log_file"
                print_info "$service_name: 로그 없음"
            fi
        fi
    done
    
    if [ $exported_count -gt 0 ]; then
        # 통합 로그 파일 생성
        local combined_file="$output_dir/combined_logs.log"
        cat "$output_dir"/*.log | sort > "$combined_file"
        
        print_success "$exported_count개 서비스 로그를 내보냈습니다"
        print_info "통합 로그 파일: $combined_file"
        
        # 압축 아카이브 생성
        local archive_name="upbit_logs_$(date +%Y%m%d_%H%M%S).tar.gz"
        tar -czf "$archive_name" -C "$(dirname "$output_dir")" "$(basename "$output_dir")"
        print_success "로그 아카이브 생성: $archive_name"
    else
        print_warning "내보낼 로그가 없습니다"
        rmdir "$output_dir" 2>/dev/null || true
    fi
}

# =============================================================================
# Helper Functions
# =============================================================================

show_available_services() {
    print_info "사용 가능한 서비스 목록:"
    
    local running_services=()
    local stopped_services=()
    
    for service in "${!SERVICE_CONTAINERS[@]}"; do
        local container_name="${SERVICE_CONTAINERS[$service]}"
        local service_name="${SERVICE_NAMES[$service]}"
        
        if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
            running_services+=("$service ($service_name)")
        else
            stopped_services+=("$service ($service_name)")
        fi
    done
    
    if [ ${#running_services[@]} -gt 0 ]; then
        echo -e "${GREEN}실행 중:${NC}"
        for service in "${running_services[@]}"; do
            echo "  ${EMOJI_SUCCESS} $service"
        done
    fi
    
    if [ ${#stopped_services[@]} -gt 0 ]; then
        echo -e "${GRAY}중지됨:${NC}"
        for service in "${stopped_services[@]}"; do
            echo "  ${EMOJI_ERROR} $service"
        done
    fi
}

show_log_statistics() {
    print_header "로그 통계"
    
    local running_services=()
    
    for service in "${!SERVICE_CONTAINERS[@]}"; do
        local container_name="${SERVICE_CONTAINERS[$service]}"
        if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
            running_services+=("$service")
        fi
    done
    
    if [ ${#running_services[@]} -eq 0 ]; then
        print_warning "실행 중인 서비스가 없습니다"
        return 1
    fi
    
    print_info "최근 1시간 로그 통계:"
    
    for service in "${running_services[@]}"; do
        local container_name="${SERVICE_CONTAINERS[$service]}"
        local service_name="${SERVICE_NAMES[$service]}"
        
        local total_lines=$(docker logs --since="1h" "$container_name" 2>&1 | wc -l)
        local error_lines=$(docker logs --since="1h" "$container_name" 2>&1 | grep -c -E "ERROR|FATAL|Exception" || echo "0")
        local warning_lines=$(docker logs --since="1h" "$container_name" 2>&1 | grep -c -E "WARN|WARNING" || echo "0")
        
        echo "  $service_name:"
        echo "    전체: ${total_lines}줄, 에러: ${error_lines}줄, 경고: ${warning_lines}줄"
    done
}

show_usage() {
    cat << EOF
🔍 Upbit Analytics Platform 로그 관리 시스템

사용법: $0 [명령] [옵션]

명령:
  show <service>        개별 서비스 로그 보기
  all                   전체 서비스 통합 로그 보기
  errors                에러 로그만 보기
  performance           성능 관련 로그 보기
  follow <service>      실시간 로그 추적
  interactive           대화형 로그 탐색기
  stats                 로그 통계 보기
  rotate                로그 회전 및 정리
  export [dir] [time]   로그 내보내기
  list                  사용 가능한 서비스 목록

옵션:
  --lines <n>           표시할 라인 수 (기본: $LOG_LINES_DEFAULT)
  --since <time>        시간 범위 (예: 1h, 30m, 2024-01-01)
  --no-timestamp        타임스탬프 숨기기

예시:
  $0 show timescaledb                    # TimescaleDB 로그 보기
  $0 all --lines 100 --since 2h         # 최근 2시간 통합 로그 100줄
  $0 follow upbit-producer               # Producer 실시간 로그
  $0 errors --since 1d                  # 최근 1일 에러 로그
  $0 export ./backup 24h                # 최근 24시간 로그 백업
  $0 interactive                         # 대화형 모드

서비스 목록:
EOF
    
    for service in "${!SERVICE_NAMES[@]}"; do
        echo "  • $service (${SERVICE_NAMES[$service]})"
    done
}

# =============================================================================
# Main Function
# =============================================================================

main() {
    setup_signal_handlers
    
    local command="${1:-interactive}"
    local lines="$LOG_LINES_DEFAULT"
    local since=""
    local service=""
    
    # Parse arguments
    shift
    while [[ $# -gt 0 ]]; do
        case $1 in
            --lines)
                lines="$2"
                shift 2
                ;;
            --since)
                since="$2"
                shift 2
                ;;
            --no-timestamp)
                LOG_TIMESTAMP_DEFAULT=false
                shift
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                if [ -z "$service" ]; then
                    service="$1"
                fi
                shift
                ;;
        esac
    done
    
    case $command in
        "show")
            show_individual_logs "$service" "$lines" false "$since"
            ;;
        "all")
            show_aggregated_logs "$lines" "${since:-1h}"
            ;;
        "errors")
            show_error_logs "$lines" "${since:-1h}"
            ;;
        "performance"|"perf")
            show_performance_logs "$lines" "${since:-30m}"
            ;;
        "follow")
            show_individual_logs "$service" "$lines" true "$since"
            ;;
        "interactive")
            start_interactive_explorer
            ;;
        "stats")
            show_log_statistics
            ;;
        "rotate")
            rotate_logs
            ;;
        "export")
            export_logs "$service" "${since:-1h}"
            ;;
        "list")
            show_available_services
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        *)
            print_error "알 수 없는 명령: $command"
            echo "도움말을 보려면: $0 help"
            exit 1
            ;;
    esac
}

# =============================================================================
# Script Execution
# =============================================================================

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi