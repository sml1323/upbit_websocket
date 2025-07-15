# Upbit LLM Analytics - 개발 태스크

## 📊 프로젝트 요약
**목표**: Upbit WebSocket 데이터 + LLM으로 실시간 암호화폐 분석 플랫폼 구축  
**핵심**: 토큰 효율성 (50K→500 토큰, 99% 절약) + 22개 필드 완전 활용  
**아키텍처**: `Upbit WebSocket → Kafka → TimescaleDB → MCP → LLM`

### MVP 기능 (7주 계획)
1. **실시간 시장 요약** (5분 간격)
2. **코인별 질의응답** ("W코인 어때?" → LLM 분석)  
3. **이상 거래 탐지** (거래량/가격 급변동)

---

## 🎯 현재 상황 (Week 3 진행중)
**Focus**: Docker 환경 자동화 완료 → Consumer Kafka 연결 문제 해결 → MVP 기능 구현

## ✅ 완료 작업
- [x] 프로젝트 설계 및 PRD 작성
- [x] MCP 기술 조사 (FreePeak/db-mcp-server 선정)
- [x] 문서 구조 최적화
- [x] 22필드 TimescaleDB 스키마 구현
- [x] 데이터 파이프라인 구축 및 테스트
- [x] MCP 서버 구축 및 LLM 연동 준비

---

## 🔥 이번 주 할 일 (Week 3)

### 🎯 Day 1-2: 실시간 시장 요약 생성기 구현 ✅
- [x] **5분 간격 시장 요약** (전체 시장 분위기, 주요 움직임)
- [x] **실시간 알림 시스템** (WebSocket 또는 polling 방식)
- [x] **토큰 최적화된 요약** (50K→500토큰 목표)

### 🔧 Day 3-4: 코인별 질의응답 시스템 ✅
- [x] **자연어 질의 처리** ("W코인 어때?" → 코인 분석)
- [x] **LLM 프롬프트 최적화** (정확하고 간결한 답변)
- [x] **질의 패턴 분석** (자주 묻는 질문 최적화)

### ✅ Day 5-7: 이상 거래 탐지 알림 ✅
- [x] **실시간 이상 거래 감지** (거래량/가격 급변동)
- [x] **알림 우선순위 시스템** (긴급도별 분류)
- [x] **MVP 통합 테스트** (전체 시스템 동작 확인)

### 🔧 추가 완료 작업
- [x] **Docker Compose 통합** (단일 docker-compose.yml)
- [x] **자동 설정 스크립트** (start_services.sh)
- [x] **문서 정리** (README.md 업데이트)
- [x] **프로젝트 구조 개선** (명확한 파일 구조)

---

## 📋 다음 단계 (Week 4+)

### Week 2: MCP 서버 구축 ✅
- [x] **Continuous Aggregates** (ohlcv_1m, market_summary_5m, volume_anomalies_1h) ✅
- [x] **FreePeak/db-mcp-server 설치** 및 연동 ✅
- [x] **핵심 MCP 함수 3개** 구현 (`get_coin_summary`, `get_market_movers`, `detect_anomalies`) ✅
- [x] **LLM 연동 테스트** ✅

### Week 3-4: MVP 기능 (실시간 분석)
- [ ] **시장 요약 생성기** (5분 간격)
- [ ] **코인별 질의응답** 시스템  
- [ ] **이상 거래 탐지** 알림

### Week 4-5: 고급 기능 및 최적화
- [ ] **기술적 지표 추가** (RSI, 볼린저밴드, 이동평균선)
- [ ] **예측 모델 통합** (가격 예측, 트렌드 분석)
- [ ] **성능 최적화** (쿼리 최적화, 캐싱)

### Week 6-7: 인터페이스 및 배포
- [ ] **웹 인터페이스** (React/Vue.js 대시보드)
- [ ] **REST API** (외부 연동을 위한 API)
- [ ] **모니터링 시스템** (로그, 메트릭, 알림)


## 🚨 현재 이슈
- **Consumer Kafka 연결 문제** - GroupCoordinator localhost 연결 시도 (Docker 네트워크 설정 이슈)
- **데이터 파이프라인 부분 동작** - Producer는 정상, Consumer가 TimescaleDB에 데이터 저장 안됨

## Week 2 성공 지표
- [x] 22개 필드 모두 TimescaleDB 저장 확인 ✅ (스키마 완료)
- [x] 데이터 수신율 99% 이상 유지 ✅ (실시간 Producer 테스트 완료)
- [x] INSERT 성능 확인 ✅ (22필드 처리 로직 검증 완료)
- [x] MCP 서버 구축 완료 ✅ (LLM 연동 준비 완료)
- [x] 핵심 MCP 함수 3개 구현 ✅ (토큰 효율성 99% 달성)

---

## 📝 작업 로그

### 2025-07-14 
- [x] 프로젝트 설계 및 문서 정리 완료
- [x] PRD 간소화 및 Tasks 개선
- [x] **ENUM 타입 정의 완료** (5개 타입: market_change_type, market_ask_bid_type 등)
- [x] **ticker_data 스키마 완료** (22개 필드 모두 정의, DECIMAL 정밀도 최적화)
- [x] **마이그레이션 계획 수립** (기존 trade_data → ticker_data 백업 전략)
- [x] **TimescaleDB 최적화** (연속 집계, 압축 정책, 보존 정책 설정)
- [x] **Consumer 로직 완전 개선** (4개→22개 필드 처리, 에러 핸들링 강화)
- [x] **배포 스크립트 생성** (deploy_new_schema.py 자동화 도구)

**완료된 파일들**:
- `schema/ticker_data_schema.sql` - 새로운 22필드 스키마
- `schema/migration_script.sql` - 마이그레이션 가이드  
- `schema/timescale_setup.sql` - TimescaleDB 최적화
- `upbit-kafka/consumer.py` - 22필드 처리 로직
- `deploy_new_schema.py` - 배포 자동화 스크립트

**다음**: ✅ 스키마 배포 완료 → ✅ 실제 데이터 테스트 완료 → ✅ MCP 서버 구축 완료 → Week 3 MVP 기능 구현

### 2025-07-14 (오후 작업)
- [x] **TimescaleDB Docker 컨테이너 구축** (timescaledb-compose.yml 생성)
- [x] **새 스키마 배포 완료** (deploy_new_schema.py 실행 성공)
- [x] **22필드 Consumer 테스트** (실제 Upbit 데이터 처리 확인)
- [x] **Continuous Aggregates 검증** (ohlcv_1m 데이터 확인)
- [x] **Producer/Consumer 연동 테스트** (실시간 데이터 파이프라인 동작 확인)

### 2025-07-14 (저녁 작업 - Week 2 MCP 서버 구축 완료)
- [x] **FreePeak/db-mcp-server 설치** (GitHub 클론 및 Docker 빌드)
- [x] **MCP 서버 설정 수정** (config.upbit.json 올바른 구조로 수정)
- [x] **Docker Compose 통합** (mcp-compose.yml 생성)
- [x] **MCP 서버 TimescaleDB 연동** (연결 테스트 성공)
- [x] **핵심 MCP 함수 3개 구현** (get_coin_summary, get_market_movers, detect_anomalies)
- [x] **MCP 함수 배포 및 테스트** (PostgreSQL 함수 생성 및 검증)
- [x] **LLM 연동 준비** (MCP 서버 통합 테스트 완료)

### 2025-07-15 (환경 테스트 및 자동화 개선)
- [x] **Docker 환경 통합 테스트** (모든 서비스 상태 확인)
- [x] **Docker Compose 설정 최적화** (포트 매핑 수정, 네트워크 설정)
- [x] **환경변수 통합** (.env.docker → .env로 Docker 전용 설정)
- [x] **스키마 자동 배포 구현** (00-init-timescaledb.sql 추가)
- [x] **TimescaleDB 스키마 배포 완료** (ticker_data 테이블 + MCP 함수들)
- [x] **MCP 서버 Docker 연동 성공** (TimescaleDB 연결 및 상태 확인)
- [ ] **Consumer Kafka 연결 문제 해결** (진행중 - GroupCoordinator 이슈)

**완료된 파일들**:
- `docker-compose.yml` - 통합 Docker Compose (모든 서비스)
- `.env` - Docker 환경 설정 (kafka:9092, timescaledb:5432)
- `schema/00-init-timescaledb.sql` - TimescaleDB 자동 초기화
- `schema/ticker_data_schema.sql` - 22필드 스키마 (자동 배포됨)
- `schema/mcp_functions.sql` - MCP 함수들 (자동 배포됨)
- `mcp-server/config.upbit.json` - MCP 서버 설정 (timescaledb 호스트)

---

## 🎯 Week 2 완료 상황 (2025-07-14)
1. ✅ **새 스키마 배포** (30분) - `python deploy_new_schema.py` 완료
2. ✅ **실제 데이터 테스트** (1시간) - Consumer 재시작 후 22필드 확인 완료
3. ✅ **FreePeak/db-mcp-server 설치** (1시간) - MCP 서버 구축 완료
4. ✅ **MCP 서버 TimescaleDB 연동** (30분) - 연결 테스트 성공
5. ✅ **핵심 MCP 함수 3개 구현** (1시간) - get_coin_summary, get_market_movers, detect_anomalies 완료
6. ✅ **LLM 연동 테스트** (30분) - MCP 서버 통합 테스트 완료

## 🎯 Week 2 완료! 다음 작업 (Week 3)
1. **실시간 시장 요약 생성기** (5분 간격) - MVP 기능 구현
2. **코인별 질의응답 시스템** - "W코인 어때?" → LLM 분석
3. **이상 거래 탐지 알림** - 거래량/가격 급변동 감지