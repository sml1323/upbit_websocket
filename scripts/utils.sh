#!/bin/bash

# =============================================================================
# Upbit Analytics Platform - Utility Functions
# =============================================================================
# Common utility functions for the launch and management scripts
# Provides: colors, progress bars, environment validation, logging
# =============================================================================

# Color constants
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly WHITE='\033[1;37m'
readonly GRAY='\033[0;90m'
readonly NC='\033[0m' # No Color

# Emoji constants
readonly EMOJI_SUCCESS="✅"
readonly EMOJI_ERROR="❌" 
readonly EMOJI_WARNING="⚠️"
readonly EMOJI_INFO="ℹ️"
readonly EMOJI_PROGRESS="🔄"
readonly EMOJI_WAITING="⏳"
readonly EMOJI_CRITICAL="🚨"
readonly EMOJI_TARGET="🎯"
readonly EMOJI_ROCKET="🚀"
readonly EMOJI_SEARCH="🔍"
readonly EMOJI_DATABASE="💾"
readonly EMOJI_NETWORK="📡"
readonly EMOJI_ANALYTICS="📊"
readonly EMOJI_ROBOT="🤖"
readonly EMOJI_CHART="📈"
readonly EMOJI_ALERT="🚨"
readonly EMOJI_DASHBOARD="🖥️"
readonly EMOJI_LINK="🔗"
readonly EMOJI_REACT="⚛️"

# Log levels
readonly LOG_DEBUG=0
readonly LOG_INFO=1
readonly LOG_WARN=2
readonly LOG_ERROR=3

# Global variables
CURRENT_LOG_LEVEL=${LOG_LEVEL:-$LOG_INFO}
SCRIPT_START_TIME=$(date +%s)

# =============================================================================
# Logging Functions
# =============================================================================

log() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    if [ "$level" -ge "$CURRENT_LOG_LEVEL" ]; then
        case $level in
            $LOG_DEBUG) echo -e "${GRAY}[DEBUG] $timestamp: $message${NC}" ;;
            $LOG_INFO)  echo -e "${BLUE}[INFO]  $timestamp: $message${NC}" ;;
            $LOG_WARN)  echo -e "${YELLOW}[WARN]  $timestamp: $message${NC}" ;;
            $LOG_ERROR) echo -e "${RED}[ERROR] $timestamp: $message${NC}" ;;
        esac
    fi
}

log_debug() { log $LOG_DEBUG "$1"; }
log_info() { log $LOG_INFO "$1"; }
log_warn() { log $LOG_WARN "$1"; }
log_error() { log $LOG_ERROR "$1"; }

# =============================================================================
# Output Functions
# =============================================================================

print_success() {
    echo -e "${GREEN}${EMOJI_SUCCESS} $1${NC}"
}

print_error() {
    echo -e "${RED}${EMOJI_ERROR} $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}${EMOJI_WARNING} $1${NC}"
}

print_info() {
    echo -e "${CYAN}${EMOJI_INFO} $1${NC}"
}

print_progress() {
    echo -e "${BLUE}${EMOJI_PROGRESS} $1${NC}"
}

print_header() {
    local title="$1"
    local length=${#title}
    local padding=$((50 - length))
    local left_pad=$((padding / 2))
    local right_pad=$((padding - left_pad))
    
    echo -e "${WHITE}"
    printf "═%.0s" {1..50}
    echo
    printf "%*s%s%*s\n" $left_pad "" "$title" $right_pad ""
    printf "═%.0s" {1..50}
    echo -e "${NC}"
}

# =============================================================================
# Progress Bar Functions
# =============================================================================

show_progress() {
    local current=$1
    local total=$2
    local message="${3:-}"
    local width=30
    
    if [ "$total" -eq 0 ]; then
        return
    fi
    
    local percentage=$((current * 100 / total))
    local filled=$((current * width / total))
    
    printf "\r${EMOJI_TARGET} %s [" "$message"
    printf "█%.0s" $(seq 1 $filled)
    printf "░%.0s" $(seq $((filled + 1)) $width)
    printf "] %d%%" $percentage
    
    if [ "$current" -eq "$total" ]; then
        echo
    fi
}

progress_spinner() {
    local pid=$1
    local message="$2"
    local spin='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0
    
    while kill -0 $pid 2>/dev/null; do
        i=$(((i+1) % ${#spin}))
        printf "\r${BLUE}%c${NC} %s" "${spin:$i:1}" "$message"
        sleep 0.1
    done
    printf "\r"
}

# =============================================================================
# Environment Validation Functions
# =============================================================================

check_command() {
    local cmd=$1
    if command -v "$cmd" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

check_docker() {
    if ! check_command docker; then
        print_error "Docker가 설치되어 있지 않습니다"
        return 1
    fi
    
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker 데몬이 실행 중이지 않습니다"
        return 1
    fi
    
    return 0
}

check_port() {
    local port=$1
    local service_name="${2:-포트 $port}"
    
    if netstat -tuln 2>/dev/null | grep -q ":$port "; then
        print_warning "$service_name ($port)이 이미 사용 중입니다"
        return 1
    fi
    return 0
}

check_disk_space() {
    local required_gb=${1:-5}
    local available_gb=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
    
    if [ "$available_gb" -lt "$required_gb" ]; then
        print_error "디스크 공간 부족: ${available_gb}GB 사용 가능, ${required_gb}GB 필요"
        return 1
    fi
    
    print_info "디스크 공간: ${available_gb}GB 사용 가능"
    return 0
}

check_memory() {
    local required_mb=${1:-2048}
    local available_mb
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        local total_bytes=$(sysctl -n hw.memsize)
        local available_mb=$((total_bytes / 1024 / 1024))
    else
        # Linux
        local available_mb=$(free -m | grep '^Mem:' | awk '{print $7}')
    fi
    
    if [ "$available_mb" -lt "$required_mb" ]; then
        print_error "메모리 부족: ${available_mb}MB 사용 가능, ${required_mb}MB 필요"
        return 1
    fi
    
    print_info "메모리: ${available_mb}MB 사용 가능"
    return 0
}

validate_environment() {
    print_info "환경 검증 중..."
    
    local checks_passed=0
    local total_checks=5
    
    # Docker 검사
    if check_docker; then
        print_success "Docker 실행 중"
        ((checks_passed++))
    fi
    
    # 포트 검사
    local ports=(5432 9092 8080 8765 8001)
    local port_check_passed=true
    for port in "${ports[@]}"; do
        if ! check_port "$port"; then
            port_check_passed=false
        fi
    done
    
    if $port_check_passed; then
        print_success "필요한 포트들이 사용 가능합니다"
        ((checks_passed++))
    fi
    
    # 디스크 공간 검사
    if check_disk_space 5; then
        ((checks_passed++))
    fi
    
    # 메모리 검사
    if check_memory 2048; then
        ((checks_passed++))
    fi
    
    # 환경변수 검사
    if [ -f ".env" ] || [ -n "${OPENAI_API_KEY:-}" ]; then
        print_success "환경변수 설정 확인됨"
        ((checks_passed++))
    else
        print_warning "OPENAI_API_KEY 환경변수가 설정되지 않았습니다"
    fi
    
    echo
    if [ "$checks_passed" -eq "$total_checks" ]; then
        print_success "모든 환경 검사를 통과했습니다 ($checks_passed/$total_checks)"
        return 0
    else
        print_warning "일부 환경 검사에 실패했습니다 ($checks_passed/$total_checks)"
        return 1
    fi
}

# =============================================================================
# Docker Helper Functions
# =============================================================================

wait_for_container() {
    local container_name=$1
    local timeout=${2:-30}
    local check_interval=${3:-2}
    
    print_progress "$container_name 컨테이너 시작 대기 중..."
    
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
            local status=$(docker inspect --format='{{.State.Status}}' "$container_name" 2>/dev/null)
            if [ "$status" = "running" ]; then
                print_success "$container_name 컨테이너가 실행 중입니다"
                return 0
            fi
        fi
        
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
        show_progress $elapsed $timeout "$container_name 대기 중"
    done
    
    print_error "$container_name 컨테이너 시작 실패 (${timeout}초 타임아웃)"
    return 1
}

wait_for_http() {
    local service_name=$1
    local url=$2
    local timeout=${3:-30}
    local check_interval=${4:-2}
    
    print_progress "$service_name HTTP 서비스 대기 중..."
    
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        if curl -sf "$url" >/dev/null 2>&1; then
            print_success "$service_name HTTP 서비스가 응답합니다"
            return 0
        fi
        
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
        show_progress $elapsed $timeout "$service_name HTTP 대기"
    done
    
    print_error "$service_name HTTP 서비스 응답 실패 (${timeout}초 타임아웃)"
    return 1
}

# =============================================================================
# Service Management Functions
# =============================================================================

start_docker_service() {
    local service_name=$1
    local compose_service="${2:-$service_name}"
    
    # 이미 실행 중인지 확인
    if docker compose ps --format "table {{.Name}}" | grep -q "^${compose_service}$" && \
       docker compose ps --format "table {{.Name}} {{.State}}" | grep "^${compose_service}" | grep -q "running"; then
        print_success "$service_name 이미 실행 중"
        return 0
    fi
    
    print_progress "$service_name 시작 중..."
    
    if docker compose up -d "$compose_service" >/dev/null 2>&1; then
        print_success "$service_name 시작됨"
        return 0
    else
        print_error "$service_name 시작 실패"
        return 1
    fi
}

stop_docker_service() {
    local service_name=$1
    local compose_service="${2:-$service_name}"
    
    print_progress "$service_name 중지 중..."
    
    if docker compose stop "$compose_service" >/dev/null 2>&1; then
        print_success "$service_name 중지됨"
        return 0
    else
        print_error "$service_name 중지 실패"
        return 1
    fi
}

# =============================================================================
# Error Handling Functions
# =============================================================================

handle_error() {
    local service=$1
    local error_msg="${2:-알 수 없는 오류}"
    
    print_error "$service 실행 실패: $error_msg"
    
    if [ "${INTERACTIVE_MODE:-true}" = "true" ]; then
        echo
        print_warning "계속 진행하시겠습니까? [y/N]"
        read -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            cleanup_and_exit 1
        fi
    else
        cleanup_and_exit 1
    fi
}

cleanup_and_exit() {
    local exit_code=${1:-0}
    
    print_info "정리 작업 중..."
    
    # 실행 시간 계산
    local end_time=$(date +%s)
    local duration=$((end_time - SCRIPT_START_TIME))
    
    if [ $exit_code -eq 0 ]; then
        print_success "작업이 성공적으로 완료되었습니다 (${duration}초 소요)"
    else
        print_error "작업이 실패하였습니다 (${duration}초 소요)"
    fi
    
    exit $exit_code
}

# =============================================================================
# Signal Handlers
# =============================================================================

setup_signal_handlers() {
    trap 'print_warning "\nCtrl+C가 감지되었습니다. 안전하게 종료 중..."; cleanup_and_exit 130' INT
    trap 'print_error "\n예기치 않은 종료가 감지되었습니다."; cleanup_and_exit 1' TERM
}

# =============================================================================
# Utility Functions
# =============================================================================

get_timestamp() {
    date '+%Y-%m-%d_%H-%M-%S'
}

format_duration() {
    local seconds=$1
    local hours=$((seconds / 3600))
    local minutes=$(((seconds % 3600) / 60))
    local secs=$((seconds % 60))
    
    if [ $hours -gt 0 ]; then
        printf "%d시간 %d분 %d초" $hours $minutes $secs
    elif [ $minutes -gt 0 ]; then
        printf "%d분 %d초" $minutes $secs
    else
        printf "%d초" $secs
    fi
}

confirm_action() {
    local message="$1"
    local default="${2:-n}"
    
    if [ "$default" = "y" ]; then
        echo -n "$message [Y/n]: "
    else
        echo -n "$message [y/N]: "
    fi
    
    read -r response
    response=${response:-$default}
    
    case $response in
        [Yy]|[Yy][Ee][Ss]) return 0 ;;
        *) return 1 ;;
    esac
}

# =============================================================================
# Initialization
# =============================================================================

# 스크립트가 직접 실행되었을 때만 초기화
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    setup_signal_handlers
    print_info "Upbit Analytics Platform 유틸리티 함수가 로드되었습니다"
fi