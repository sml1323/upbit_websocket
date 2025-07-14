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

## 🎯 현재 상황 (Week 1 → Week 2)
**Focus**: ✅ Week 1 완료! → Week 2 MCP 서버 구축 시작

## ✅ 완료 작업
- [x] 프로젝트 설계 및 PRD 작성
- [x] MCP 기술 조사 (FreePeak/db-mcp-server 선정)
- [x] 문서 구조 최적화

---

## 🔥 이번 주 할 일 (Week 1)

### 🎯 Day 1-2: 데이터베이스 스키마 구현  
- [x] **ENUM 타입 정의** (market_change_type, market_ask_bid_type 등) ✅
- [x] **ticker_data 테이블 재설계** (22개 필드 → 기존 4개에서 확장) ✅  
- [x] **기존 데이터 백업** 및 마이그레이션 계획 ✅
- [x] **TimescaleDB 하이퍼테이블 설정** ✅

### 🔧 Day 3-4: Consumer 로직 개선
- [x] **consumer.py 수정** (JSON 파싱 4개→22개 필드) ✅
- [x] **데이터 타입 변환** (DECIMAL, ENUM 매핑) ✅
- [x] **에러 핸들링 강화** (데이터 검증, 예외 처리) ✅

### ✅ Day 5-7: 테스트 및 검증  
- [ ] **실제 데이터 테스트** (성능, 정확성)
- [ ] **기본 모니터링 설정**

---

## 📋 다음 단계 (Week 2+)

### Week 2: MCP 서버 구축
- [x] **Continuous Aggregates** (ohlcv_1m, market_summary_5m, volume_anomalies_1h) ✅
- [ ] **FreePeak/db-mcp-server 설치** 및 연동
- [ ] **핵심 MCP 함수 3개** 구현 (`get_coin_summary`, `get_market_movers`, `detect_anomalies`)
- [ ] **LLM 연동 테스트**

### Week 3-4: MVP 기능 (실시간 분석)
- [ ] **시장 요약 생성기** (5분 간격)
- [ ] **코인별 질의응답** 시스템  
- [ ] **이상 거래 탐지** 알림

### Week 5-7: 확장 기능
- [ ] 기술적 지표 (RSI, 볼린저밴드)
- [ ] 웹 인터페이스
- [ ] 모니터링 시스템

## 🚨 현재 이슈
- **없음** - 현재 블로커 없음

## Week 1 성공 지표
- [x] 22개 필드 모두 TimescaleDB 저장 확인 ✅ (스키마 완료)
- [ ] 데이터 수신율 99% 이상 유지 (배포 후 테스트 필요)
- [ ] INSERT 성능 확인 (배포 후 테스트 필요)

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

**다음**: 스키마 배포 → 실제 데이터 테스트 → MCP 서버 구축

---

## 🎯 지금 시작할 작업 (Week 2)
1. **새 스키마 배포** (30분) - `python deploy_new_schema.py`
2. **실제 데이터 테스트** (1시간) - Consumer 재시작 후 22필드 확인
3. **FreePeak/db-mcp-server 설치** (1시간) - MCP 서버 구축 시작