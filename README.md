# Upbit LLM Analytics Platform
# **업비트 WebSocket + LLM 실시간 암호화폐 분석 플랫폼**

---

## **프로젝트 개요**
이 프로젝트는 **업비트(Upbit) 웹소켓 API**를 통해 실시간으로 암호화폐 거래 데이터(22개 필드)를 수집하고, **Kafka → TimescaleDB → MCP → LLM** 파이프라인을 통해 **토큰 효율성 99% 절약**(50K→500 토큰)으로 실시간 시장 분석을 제공하는 플랫폼입니다.

---

## **핵심 기능**

### 🎯 MVP 기능
1. **실시간 시장 요약** - 5분마다 전체 시장 상황 자연어 요약
2. **코인별 질의응답** - "W코인 지금 어때?" → LLM 종합 분석  
3. **이상 거래 탐지** - 거래량/가격 급변동 감지 및 LLM 해석

### 🔧 구성 요소
1. **Upbit WebSocket API** - 22개 필드 실시간 데이터 수집
2. **Kafka** - 고성능 메시지 브로커 (Docker)  
3. **TimescaleDB** - 시계열 최적화 + 연속 집계 (Continuous Aggregates)
4. **MCP Server** - LLM 연동을 위한 효율적 데이터 제공
5. **LLM (Claude)** - 자연어 분석 및 질의응답

---

## **아키텍처 구조**
```bash
┌─────────────────┐    ┌──────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│ Upbit WebSocket │───►│  Kafka   │───►│ TimescaleDB  │───►│ MCP Server  │───►│ LLM (Claude)│
│ (22개 필드)     │    │(메시지큐)│    │(시계열 DB)   │    │(토큰 최적화)│    │(자연어 분석)│
└─────────────────┘    └──────────┘    └──────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │연속 집계 DB │
                                       │(1분/5분/1시간)│
                                       └─────────────┘
```

### 토큰 효율성 핵심
- **Raw 데이터**: 50,000 토큰 (22필드 × 수백 코인)
- **MCP 집계**: 500 토큰 (계산된 지표만)
- **절약률**: 99% (50K → 500)

---

## **설치 및 실행 방법**

### **🚀 빠른 시작 (자동 배포)**
```bash
# 1. 환경 설정
pip install -r requirements.txt

# 2. Kafka 실행  
docker-compose -f kafka-compose.yml up -d

# 3. 데이터베이스 스키마 배포 (22필드 + TimescaleDB 최적화)
python deploy_new_schema.py

# 4. 데이터 파이프라인 시작
cd upbit-kafka
python producer.py &    # 데이터 수집
python consumer.py &    # 데이터 저장
```

---

### **📋 단계별 설치**

#### **1. 기본 환경 설정**
```bash
# Docker 설치 (Ubuntu)
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Python 의존성 설치
pip install -r requirements.txt
```

#### **2. Kafka 클러스터 시작**
```bash
docker-compose -f kafka-compose.yml up -d
```

#### **3. TimescaleDB 설정**
```bash
# TimescaleDB 설치 (docs/README-timescaledb.md 참고)
# 또는 자동 스키마 배포
python deploy_new_schema.py
```

#### **4. 데이터 파이프라인 실행**
```bash
# Producer: Upbit WebSocket → Kafka
cd upbit-kafka
python producer.py

# Consumer: Kafka → TimescaleDB (22필드)
python consumer.py
```

#### **5. MCP 서버 설정 (Week 2)**
```bash
# Week 2에서 구현 예정
# FreePeak/db-mcp-server 설치 및 LLM 연동
```



## **🚀 개발 로드맵**

### ✅ Week 1 (완료) - 데이터베이스 스키마 구현
- **ENUM 타입 정의** (5개)
- **ticker_data 테이블 재설계** (4→22 필드)  
- **TimescaleDB 최적화** (연속 집계, 압축, 인덱싱)
- **Consumer 로직 개선** (22필드 처리, 에러 핸들링)
- **배포 자동화** (deploy_new_schema.py)

### 🔄 Week 2 (진행 중) - MCP 서버 구축  
- FreePeak/db-mcp-server 설치 및 연동
- 핵심 MCP 함수 3개 구현  
- LLM 연동 테스트

### 📈 Week 3-4 - MVP 기능 구현
- 실시간 시장 요약 생성기 (5분 간격)
- 코인별 질의응답 시스템
- 이상 거래 탐지 알림

### 🌐 Week 5-7 - 확장 기능
- 웹 인터페이스 (FastAPI)
- 기술적 지표 분석  
- 모니터링 시스템

---

## **📋 주요 파일 구조**
```
upbit_websocket/
├── schema/                 # 데이터베이스 스키마
│   ├── ticker_data_schema.sql
│   ├── migration_script.sql
│   └── timescale_setup.sql
├── upbit-kafka/           # 데이터 파이프라인
│   ├── producer.py        # WebSocket → Kafka
│   └── consumer.py        # Kafka → TimescaleDB
├── deploy_new_schema.py   # 자동 배포 스크립트
└── docs/                  # 설치 가이드
```
---

## **데이터 스키마 (22개 필드)**

### 📊 ticker_data 테이블
| 필드 그룹 | 컬럼명 | 타입 | 설명 |
|-----------|--------|------|------|
| **기본** | `time` | `TIMESTAMPTZ` | 처리 시각 |
| | `code` | `TEXT` | 코인 코드 (KRW-BTC) |
| | `type` | `TEXT` | 메시지 타입 (ticker) |
| **가격** | `opening_price` | `DECIMAL(20,8)` | 시가 |
| | `high_price` | `DECIMAL(20,8)` | 고가 |
| | `low_price` | `DECIMAL(20,8)` | 저가 |
| | `trade_price` | `DECIMAL(20,8)` | 현재가 |
| | `prev_closing_price` | `DECIMAL(20,8)` | 전일 종가 |
| **변동** | `change` | `ENUM` | 변동 방향 (RISE/FALL/EVEN) |
| | `change_price` | `DECIMAL(20,8)` | 변동 금액 |
| | `change_rate` | `DECIMAL(10,8)` | 변동률 (0.0404 = 4.04%) |
| **거래량** | `trade_volume` | `DECIMAL(20,8)` | 체결 거래량 |
| | `acc_trade_volume` | `DECIMAL(20,8)` | 누적 거래량 |
| | `acc_trade_price` | `DECIMAL(25,8)` | 누적 거래대금 |
| | `ask_bid` | `ENUM` | 매수/매도 구분 (ASK/BID) |
| **24시간** | `acc_trade_volume_24h` | `DECIMAL(20,8)` | 24시간 거래량 |
| | `acc_trade_price_24h` | `DECIMAL(25,8)` | 24시간 거래대금 |
| **52주** | `highest_52_week_price` | `DECIMAL(20,8)` | 52주 최고가 |
| | `lowest_52_week_price` | `DECIMAL(20,8)` | 52주 최저가 |
| **시장** | `market_state` | `ENUM` | 시장 상태 (ACTIVE/SUSPENDED) |
| | `market_warning` | `ENUM` | 시장 경고 (NONE/CAUTION/WARNING) |
| **타임스탬프** | `trade_timestamp` | `BIGINT` | 거래 타임스탬프 |
| | `timestamp` | `BIGINT` | 메시지 타임스탬프 |

### 🔄 연속 집계 테이블  
- **ohlcv_1m**: 1분 캔들 데이터
- **market_summary_5m**: 5분 시장 요약  
- **volume_anomalies_1h**: 시간별 이상 거래 탐지

---

## **⚙️ 환경 설정**

### .env 파일 설정
```bash
# Kafka 설정
KAFKA_SERVERS=localhost:9092
KAFKA_TOPIC=upbit_ticker
KAFKA_GROUP_ID=default_group

# TimescaleDB 설정  
TIMESCALEDB_DBNAME=coin
TIMESCALEDB_USER=postgres
TIMESCALEDB_PASSWORD=postgres
TIMESCALEDB_HOST=localhost
TIMESCALEDB_PORT=5432
```

### 서비스 접속 정보
- **Kafka**: localhost:9092
- **PostgreSQL**: localhost:5432  
- **TimescaleDB 확장**: 자동 활성화

---

## **🔧 트러블슈팅**

### 자주 발생하는 문제

**1. Kafka 연결 실패**
```bash
# Kafka 컨테이너 상태 확인
docker ps | grep kafka

# 재시작
docker-compose -f kafka-compose.yml restart
```

**2. TimescaleDB 연결 실패** 
```bash
# PostgreSQL 서비스 확인
sudo systemctl status postgresql

# 데이터베이스 접속 테스트
psql -h localhost -U postgres -d coin
```

**3. 스키마 배포 실패**
```bash
# 수동 스키마 실행
psql -h localhost -U postgres -d coin -f schema/ticker_data_schema.sql
```

**4. Consumer 에러**
- JSON 디코딩 에러: 네트워크 연결 확인
- DB 삽입 실패: 스키마 배포 상태 확인

---

## **📞 지원**

- **Issues**: GitHub Issues 탭 활용
- **Documentation**: `/docs` 폴더 참고  
- **Schema Guide**: `schema/` 폴더의 SQL 파일들

---

**🎯 목표**: 토큰 효율성 99% 절약으로 실시간 암호화폐 LLM 분석 플랫폼 구축!
