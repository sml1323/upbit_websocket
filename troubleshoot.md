# 🔧 Troubleshooting Guide

Upbit Analytics Platform에서 발생할 수 있는 문제들과 해결 방법을 정리했습니다.

## 🚨 일반적인 문제들

### 1. 데이터베이스 연결 실패

**문제**: `role "upbit_user" does not exist` 오류
```bash
FATAL: role "upbit_user" does not exist
```

**해결방법**:
```bash
# 1. 컨테이너와 볼륨 완전 삭제
docker compose down -v

# 2. 시스템 재시작
./start.sh --clean
```

**원인**: 데이터베이스 초기화 스크립트가 제대로 실행되지 않음

---

### 2. 스키마 함수 누락

**문제**: `function get_comprehensive_prediction does not exist` 오류
```bash
function get_comprehensive_prediction(unknown, integer) does not exist
```

**해결방법**:
```bash
# 1. 수동으로 스키마 배포
docker exec timescaledb psql -U upbit_user -d upbit_analytics -f /docker-entrypoint-initdb.d/01-auto-deploy.sql

# 2. 또는 전체 재시작
./start.sh --clean
```

**원인**: 스키마 자동 배포 실패

---

### 3. 포트 충돌

**문제**: `Port already in use` 오류
```bash
Error: bind: address already in use
```

**해결방법**:
```bash
# 1. 환경 검증 실행
python shared/validate-env.py

# 2. 사용 중인 포트 확인
lsof -i :5432  # TimescaleDB
lsof -i :9092  # Kafka
lsof -i :8001  # Dashboard

# 3. 프로세스 종료 또는 포트 변경
```

---

### 4. Docker 이미지 빌드 실패

**문제**: Docker 이미지 빌드 중 오류
```bash
ERROR: failed to solve: process "/bin/sh -c pip install..." didn't complete
```

**해결방법**:
```bash
# 1. Docker 캐시 정리
docker system prune -f

# 2. 베이스 이미지 다시 빌드
docker build -f shared/Dockerfile.python-base -t upbit-python-base:latest . --no-cache

# 3. 서비스 이미지 다시 빌드
docker compose build --no-cache
```

---

### 5. 의존성 대기 실패

**문제**: 서비스가 의존성을 기다리다가 타임아웃
```bash
❌ TimescaleDB failed to become ready after 30 attempts
```

**해결방법**:
```bash
# 1. 헬스체크 스크립트 직접 실행
python shared/health-check.py service-name timescaledb kafka

# 2. 로그 확인
docker logs timescaledb
docker logs kafka

# 3. 수동으로 순서대로 시작
docker compose up -d timescaledb
sleep 30
docker compose up -d kafka
sleep 30
docker compose up -d upbit-producer upbit-consumer
```

---

## 🔍 디버깅 명령어

### 환경 검증
```bash
# 전체 환경 검증
python shared/validate-env.py

# 환경 변수 템플릿 생성
python shared/validate-env.py --generate-template > .env.template
```

### 서비스 상태 확인
```bash
# 모든 서비스 상태
docker compose ps

# 특정 서비스 로그
docker logs <service-name> --tail=50

# 실시간 로그 모니터링
docker compose logs -f <service-name>
```

### 데이터베이스 확인
```bash
# 데이터베이스 연결
docker exec -it timescaledb psql -U upbit_user -d upbit_analytics

# 테이블 목록
\dt

# 함수 목록
\df

# 데이터 확인
SELECT COUNT(*) FROM ticker_data;
```

### 헬스체크
```bash
# 개별 서비스 헬스체크
python shared/health-check.py upbit-producer kafka
python shared/health-check.py upbit-consumer kafka timescaledb-schema

# 전체 시스템 헬스체크
python shared/health-check.py system-check timescaledb kafka
```

---

## 🛠️ 복구 절차

### 전체 시스템 재시작
```bash
# 1. 모든 서비스 종료
docker compose down -v

# 2. 시스템 정리
docker system prune -f

# 3. 깔끔한 시작
./start.sh --clean
```

### 부분 재시작
```bash
# 1. 특정 서비스만 재시작
docker compose restart <service-name>

# 2. 데이터 파이프라인만 재시작
docker compose restart upbit-producer upbit-consumer

# 3. 인프라만 재시작
docker compose restart timescaledb kafka zookeeper redis
```

---

## 📋 로그 분석

### 중요한 로그 패턴

**성공적인 데이터 수집**:
```
[INFO] Inserted ticker data: KRW-BTC @ 162000000.0 (+0.5%)
```

**Kafka 연결 성공**:
```
[INFO] KRW-BTC 키로 카프카에 메세지 전송
```

**데이터베이스 연결 성공**:
```
[INFO] Connected to TimescaleDB
```

**서비스 시작 성공**:
```
[INFO] 실시간 시장 요약 서비스 시작
[INFO] 코인 Q&A 시스템 초기화 완료
```

---

## 🚀 성능 최적화

### 메모리 사용량 최적화
```bash
# Docker 메모리 사용량 확인
docker stats

# 특정 서비스 메모리 제한
docker compose up -d --scale upbit-producer=1 --memory=512m
```

### 데이터베이스 최적화
```sql
-- 연결 수 확인
SELECT count(*) FROM pg_stat_activity;

-- 슬로우 쿼리 확인
SELECT query, mean_exec_time, calls 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC;
```

---

## 📞 지원 요청 시 제공할 정보

문제 발생 시 다음 정보를 수집해 주세요:

1. **환경 정보**:
   ```bash
   python shared/validate-env.py > env-check.log 2>&1
   ```

2. **시스템 상태**:
   ```bash
   docker compose ps > system-status.log
   ```

3. **로그 파일**:
   ```bash
   docker compose logs > system-logs.log 2>&1
   ```

4. **오류 재현 단계**:
   - 정확한 명령어 순서
   - 오류 메시지 전문
   - 발생 시점

---

## 🔄 정기 유지보수

### 주간 점검
```bash
# 1. 로그 크기 확인
docker system df

# 2. 데이터베이스 상태 확인
docker exec timescaledb psql -U upbit_user -d upbit_analytics -c "SELECT COUNT(*) FROM ticker_data;"

# 3. 시스템 정리
docker system prune -f
```

### 월간 점검
```bash
# 1. 이미지 업데이트
docker compose pull

# 2. 전체 재시작
./start.sh --clean

# 3. 성능 모니터링
docker stats > performance-report.log
```

---

이 가이드를 따라도 문제가 해결되지 않으면, 로그 파일과 함께 이슈를 보고해 주세요.