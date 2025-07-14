# 🚀 Upbit LLM Analytics

실시간 암호화폐 데이터 분석 및 LLM 기반 질의응답 시스템

## 📊 주요 기능

### ✅ 완료된 기능 (Week 3)
1. **실시간 시장 요약 생성기** - 5분 간격으로 전체 시장 분위기 분석
2. **코인별 질의응답 시스템** - "BTC 어때?" 같은 자연어 질의 처리
3. **이상 거래 탐지 알림** - 거래량/가격 급변동 실시간 감지

### 🔧 기술 스택
- **데이터 수집**: Upbit WebSocket API
- **메시지 브로커**: Apache Kafka
- **데이터베이스**: PostgreSQL + TimescaleDB
- **LLM 연동**: OpenAI GPT-4o-mini
- **실시간 알림**: WebSocket
- **인프라**: Docker Compose

## 🚀 빠른 시작

### 1. 환경 설정
```bash
# 저장소 클론
git clone <repository-url>
cd upbit_websocket

# 환경 변수 설정 (.env 파일 생성)
cp .env.example .env
# OpenAI API 키 설정 필요
```

### 2. 서비스 시작
```bash
# 모든 인프라 서비스 시작 (자동 설정 포함)
./start_services.sh
```

### 3. 애플리케이션 실행
```bash
# 터미널 1: 데이터 수집
python upbit-kafka/producer.py

# 터미널 2: 데이터 저장
python upbit-kafka/consumer.py

# 터미널 3: 실시간 시장 요약
python realtime_market_summary.py

# 터미널 4: 코인 질의응답
python coin_qa_system.py
```

### 4. 웹 클라이언트 접속
```bash
# 브라우저에서 열기
open market_summary_client.html
```

## 🎯 사용 예시

### 실시간 시장 요약
- 5분마다 자동 업데이트
- WebSocket 실시간 알림
- 토큰 효율적 요약 (50K→500토큰)

### 코인 질의응답
```
사용자: "BTC 어때?"
시스템: "📊 KRW-BTC 분석
현재 95,500,000원 (+1.06%)
상승 추세이며 거래량 정상 수준
기술적으로 중립 상태"
```

## 🔧 서비스 접속 정보

| 서비스 | 포트 | 접속 정보 |
|--------|------|-----------|
| TimescaleDB | 5432 | upbit_user/upbit_password |
| Kafka | 9092 | localhost:9092 |
| MCP Server | 9093 | localhost:9093 |
| Redis | 6379 | localhost:6379 |
| WebSocket | 8765 | ws://localhost:8765 |

## 📁 프로젝트 구조

```
upbit_websocket/
├── docker-compose.yml              # 통합 Docker Compose 설정
├── start_services.sh              # 서비스 시작 스크립트
├── .env                           # 환경 변수 설정
├── upbit-kafka/
│   ├── producer.py                # Upbit 데이터 수집
│   └── consumer.py                # 데이터 저장
├── realtime_market_summary.py     # 실시간 시장 요약
├── coin_qa_system.py              # 코인 질의응답
├── market_summary_client.html     # 웹 클라이언트
├── schema/
│   ├── ticker_data_schema.sql     # 데이터베이스 스키마
│   └── mcp_functions.sql          # MCP 함수들
└── tasks.md                       # 개발 진행사항
```

## ⚙️ 설정 파일

### .env 파일 예시
```bash
# Kafka 설정
KAFKA_SERVERS=localhost:9092
KAFKA_TOPIC=upbit_ticker
KAFKA_GROUP_ID=default_group

# TimescaleDB 설정
TIMESCALEDB_HOST=localhost
TIMESCALEDB_PORT=5432
TIMESCALEDB_DBNAME=upbit_analytics
TIMESCALEDB_USER=upbit_user
TIMESCALEDB_PASSWORD=upbit_password

# OpenAI API 설정
OPENAI_API_KEY=your_openai_api_key

# 기타 설정
LOG_LEVEL=INFO
```

## 🔍 주요 기능 설명

### 1. 실시간 시장 요약
- **목적**: 5분 간격으로 전체 시장 분위기 파악
- **특징**: 토큰 효율적 요약 (99% 절약)
- **출력**: WebSocket 실시간 브로드캐스트

### 2. 코인별 질의응답
- **목적**: 자연어로 특정 코인 정보 조회
- **특징**: GPT-4o-mini 기반 분석
- **예시**: "BTC 어때?", "비트코인 투자해도 될까?"

### 3. 이상 거래 탐지
- **목적**: 거래량/가격 급변동 실시간 감지
- **특징**: 통계적 임계값 기반 알림
- **출력**: 심각도별 분류 (critical/high/medium/low)

## 🛠️ 개발 명령어

```bash
# 서비스 중지
docker compose down

# 로그 확인
docker compose logs -f [서비스명]

# 데이터베이스 접속
docker exec -it timescaledb psql -U upbit_user -d upbit_analytics

# 캐시 정리
docker system prune -f
```

## 📈 성능 지표

- **데이터 수신율**: 99% 이상
- **토큰 효율성**: 50K→500토큰 (99% 절약)
- **응답 시간**: 평균 2-3초
- **동시 접속**: WebSocket 다중 클라이언트 지원

## 🎯 다음 단계 (Week 4+)

- [ ] 기술적 지표 추가 (RSI, 볼린저밴드)
- [ ] 예측 모델 통합
- [ ] 웹 대시보드 구축
- [ ] REST API 제공
- [ ] 모니터링 시스템 구축

## 📞 지원

문제 발생 시 다음을 확인하세요:

1. **서비스 상태**: `docker compose ps`
2. **로그 확인**: `docker compose logs -f`
3. **환경 변수**: `.env` 파일 설정
4. **네트워크**: 포트 충돌 확인

---

🚀 **Week 3 MVP 기능 완료!** 실시간 분석 시스템이 준비되었습니다.