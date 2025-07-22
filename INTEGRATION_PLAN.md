# 🚀 Upbit Analytics Platform 통합 실행 스크립트 계획

## 📋 **프로젝트 개요**
단일 명령으로 전체 Upbit Analytics Platform을 실행할 수 있는 통합 스크립트 시스템 구축

## 🎯 **핵심 목표**
- **원클릭 실행**: `./launch-upbit-analytics.sh` 하나로 전체 시스템 구동
- **단계별 검증**: 각 서비스의 헬스체크와 의존성 관리
- **사용자 친화적**: 진행상황 표시, 컬러풀한 출력, 에러 처리
- **유연한 모드**: 개발/운영/최소/전체 모드 지원

---

## 📊 **시스템 아키텍처 분석**

### **의존성 계층구조**
```
Level 1: 인프라 서비스
├── TimescaleDB (5432)
├── Zookeeper (2181) 
├── Kafka (9092)
└── Redis (6379)

Level 2: 데이터 파이프라인  
├── upbit-producer (WebSocket)
└── upbit-consumer (DB 저장)

Level 3: 분석 서비스
├── mvp-coin-qa (8080)
├── mvp-market-summary (8765)
├── mvp-anomaly-detection (백그라운드)
└── dashboard-server (8001)

Level 4: 선택적 서비스
├── MCP Server (9093)
└── Next.js Dashboard (3000)
```

---

## 🛠 **구현 계획**

### **1. 메인 통합 스크립트**
**파일**: `launch-upbit-analytics.sh`

**실행 모드**:
- `--dev`: 개발 모드 (상세 로그, 포그라운드 실행)
- `--prod`: 운영 모드 (백그라운드, 최적화된 설정)
- `--minimal`: 핵심만 (DB + 데이터수집 + Q&A)
- `--full`: 전체 (MCP서버, Next.js 포함)

**주요 기능**:
- ✅ 환경 검증 (Docker, 포트, 리소스)
- ✅ 단계별 서비스 시작 + 헬스체크
- ✅ 실시간 진행상황 표시
- ✅ 에러 처리 및 롤백
- ✅ 키보드 인터럽트 처리 (Ctrl+C)

### **2. 지원 스크립트 모음**

**`scripts/health-check.sh`**
- 각 서비스별 헬스체크 함수
- 타임아웃 및 재시도 로직
- 상태별 컬러 출력

**`scripts/logs.sh`** 
- 통합 로그 뷰어
- 개별 서비스 로그 접근
- 실시간 로그 추적

**`scripts/stop-all.sh`**
- 우아한 서비스 종료
- 데이터 무결성 보장
- 리소스 정리

**`scripts/utils.sh`**
- 공통 유틸리티 함수
- 컬러 출력, 프로그레스바
- 환경 검증 로직

---

## ⚡ **실행 시퀀스 설계**

### **Phase 1: 환경 검증** (5초)
```bash
[🔍] Docker 버전 확인...                    ✅
[🔍] 필요한 포트 검사 (5432,9092,8080...)   ✅
[🔍] 디스크/메모리 여유공간 확인...          ✅
[🔍] 환경변수 검증...                      ✅
```

### **Phase 2: 인프라 시작** (60초)
```bash
[🚀] TimescaleDB 시작 중...      [████████████] 100% ✅
[🚀] Zookeeper 시작 중...       [████████████] 100% ✅  
[🚀] Kafka 시작 중...          [████████████] 100% ✅
[🚀] Redis 시작 중...          [████████████] 100% ✅
[📊] 스키마 배포 확인...         [████████████] 100% ✅
```

### **Phase 3: 데이터 파이프라인** (30초)
```bash
[📡] Upbit Producer 시작...     [████████████] 100% ✅
[💾] Data Consumer 시작...      [████████████] 100% ✅
[⏳] 첫 데이터 수신 대기...       [████████████] 100% ✅
```

### **Phase 4: 분석 서비스** (45초)
```bash
[🤖] Coin Q&A System...        [████████████] 100% ✅
[📈] Market Summary...         [████████████] 100% ✅
[🚨] Anomaly Detection...      [████████████] 100% ✅
[🖥️] Dashboard Server...       [████████████] 100% ✅
```

### **Phase 5: 선택적 서비스** (--full 모드)
```bash
[🔗] MCP Server...             [████████████] 100% ✅
[⚛️] Next.js Dashboard...       [████████████] 100% ✅
```

---

## 🎨 **사용자 경험 설계**

### **시작 화면**
```
🚀 Upbit Analytics Platform Launcher v1.0
===============================================
모드: --full | 예상 시간: ~3분 | 포트: 5432,8080,8765,3000...

[1/5] 환경 검증 중...
[2/5] 인프라 서비스 시작...
[3/5] 데이터 파이프라인 구성...
[4/5] 분석 서비스 배포...
[5/5] 대시보드 활성화...

🎯 진행상황: [██████████████████████████████] 100%
```

### **완료 대시보드**
```
✅ Upbit Analytics Platform 실행 완료!
==========================================
🌐 서비스 접속 정보:
├── Coin Q&A:        http://localhost:8080
├── Market Summary:  http://localhost:8765  
├── Dashboard:       http://localhost:8001
└── Next.js App:     http://localhost:3000

📊 실시간 상태:
├── 수집된 데이터:   127,450건
├── 활성 코인:      177개
├── 급등 알림:      3건 (Critical)
└── 시스템 상태:    🟢 정상

⌨️  명령어:
├── 로그 보기:      ./scripts/logs.sh
├── 상태 확인:      ./scripts/health-check.sh  
└── 시스템 종료:    ./scripts/stop-all.sh
```

---

## 📝 **다음 세션 실행 계획**

### **우선순위 작업**
1. **메인 스크립트 구현** - `launch-upbit-analytics.sh`
2. **헬스체크 시스템** - `scripts/health-check.sh`
3. **유틸리티 함수** - `scripts/utils.sh`
4. **테스트 및 검증**

### **예상 구현 시간**
- 스크립트 작성: 1-2시간
- 테스트 및 디버깅: 30분-1시간
- 문서화: 30분

### **구현 체크리스트**
- [ ] `scripts/` 디렉토리 생성
- [ ] `scripts/utils.sh` - 공통 함수 구현
- [ ] `scripts/health-check.sh` - 헬스체크 로직
- [ ] `launch-upbit-analytics.sh` - 메인 스크립트
- [ ] `scripts/logs.sh` - 로그 관리
- [ ] `scripts/stop-all.sh` - 안전한 종료
- [ ] 테스트 시나리오 실행
- [ ] 문서 업데이트

### **기술적 구현 세부사항**

#### **헬스체크 로직**
```bash
# TimescaleDB
wait_for_service "TimescaleDB" "docker exec timescaledb pg_isready -U upbit_user" 30

# Kafka  
wait_for_service "Kafka" "docker exec kafka kafka-topics.sh --list --bootstrap-server localhost:9092" 30

# 웹서비스
wait_for_http "Coin Q&A" "http://localhost:8080/health" 15
```

#### **프로그레스바 구현**
```bash
show_progress() {
    local current=$1
    local total=$2  
    local width=30
    local percentage=$((current * 100 / total))
    local filled=$((current * width / total))
    
    printf "\r🎯 진행상황: ["
    printf "█%.0s" $(seq 1 $filled)
    printf "░%.0s" $(seq $((filled + 1)) $width)
    printf "] %d%%" $percentage
}
```

#### **에러 처리**
```bash
handle_error() {
    local service=$1
    local error_msg=$2
    
    echo "❌ $service 시작 실패: $error_msg"
    echo "🤔 계속 진행하시겠습니까? [y/N]"
    read -n 1 -r
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        cleanup_and_exit
    fi
}
```

---

## 🎯 **목표**
**사용자가 `./launch-upbit-analytics.sh --full` 한 번으로 전체 시스템을 완벽하게 실행할 수 있도록!**

---

**날짜**: 2025-07-22  
**상태**: 계획 완료, 구현 대기  
**담당**: 다음 세션에서 시작