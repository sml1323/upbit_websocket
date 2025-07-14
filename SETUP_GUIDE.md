# Upbit LLM Analytics - 설정 가이드

## 🚀 빠른 시작 (새 세션용)

```bash
# 1. 모든 서비스 한번에 시작
./quick_start.sh

# 2. 개별 테스트
python test_mcp_connection.py
python upbit-kafka/producer.py &
python upbit-kafka/consumer.py
```

## 📋 현재 구성 상태

### ✅ 완료된 구성
- **TimescaleDB**: 22필드 ticker_data 스키마 + Continuous Aggregates
- **MCP Server**: FreePeak/db-mcp-server + TimescaleDB 연동
- **Kafka**: Producer/Consumer 실시간 데이터 파이프라인
- **Docker Compose**: 통합 서비스 관리

### 🔧 핵심 파일들
```
├── mcp-compose.yml              # 통합 Docker Compose (TimescaleDB + MCP + Kafka)
├── timescaledb-compose.yml      # TimescaleDB 단독 실행용
├── kafka-compose.yml            # Kafka 단독 실행용
├── db-mcp-server/
│   └── config.upbit.json        # MCP 서버 설정 (connections 구조)
├── schema/
│   ├── ticker_data_schema.sql   # 22필드 스키마
│   ├── timescale_setup.sql      # Continuous Aggregates
│   └── mcp_functions.sql        # 비즈니스 로직 함수들
└── upbit-kafka/
    ├── producer.py              # Upbit WebSocket → Kafka
    └── consumer.py              # Kafka → TimescaleDB
```

## 🚨 흔한 문제 해결

### 1. MCP 서버 연결 실패
**증상**: `"no database configuration provided"`
**해결**: 
```bash
# config.upbit.json 구조 확인
{
  "connections": [    # ← "databases" 아님!
    {
      "name": "upbit_analytics",  # ← "database" 아님!
      "host": "timescaledb"       # ← Docker 서비스명
    }
  ]
}
```

### 2. TimescaleDB 연결 실패
**증상**: `role "upbit_user" does not exist`
**해결**:
```bash
# TimescaleDB 재시작
docker restart timescaledb
sleep 10
docker exec timescaledb psql -h localhost -U upbit_user -d upbit_analytics -c "SELECT 1;"
```

### 3. Kafka 포트 충돌
**증상**: `port already in use`
**해결**: MCP 서버는 9093 포트 사용하도록 설정됨

### 4. 권한 문제
**증상**: `permission denied`
**해결**:
```bash
chmod +x quick_start.sh
chmod 666 /var/run/docker.sock  # macOS/Linux
```

## 🔍 상태 확인 명령어

```bash
# 1. 컨테이너 상태
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 2. 서비스 로그
docker logs upbit-mcp-server
docker logs timescaledb
docker logs kafka

# 3. 연결 테스트
curl http://localhost:9093/status
python test_mcp_connection.py

# 4. 데이터 확인
docker exec timescaledb psql -h localhost -U upbit_user -d upbit_analytics -c "
SELECT COUNT(*) FROM ticker_data;
SELECT COUNT(*) FROM ohlcv_1m;
"
```

## 🎯 다음 단계 (Week 2 마무리)

### 1. 핵심 MCP 함수 구현
**파일**: `schema/mcp_functions.sql`
**구현할 함수들**:
- `get_coin_summary(code, timeframe)` - 코인 종합 분석
- `get_market_movers(type, limit, timeframe)` - 시장 활발한 코인
- `detect_anomalies(timeframe, sensitivity)` - 이상 거래 탐지

### 2. LLM 연동 테스트
**파일**: `mcp/llm_integration_test.py`
**테스트 시나리오**:
- Claude/GPT와 MCP 서버 연동
- 토큰 효율성 측정 (50K→500 토큰)
- 실시간 질의응답 테스트

### 3. 성능 검증
- **응답 속도**: 3초 이하
- **토큰 효율성**: 99% 절약
- **데이터 정확성**: 실시간 sync

## 📈 현재 달성률

**Week 1**: ✅ 100% 완료 (22필드 스키마 + 실시간 파이프라인)
**Week 2**: ✅ 66% 완료 (MCP 서버 + DB 연동)

**남은 작업**:
- [ ] 핵심 MCP 함수 3개 구현
- [ ] LLM 연동 테스트
- [ ] MVP 기능 구현

## 🆘 도움말

문제 발생 시:
1. `./quick_start.sh` 재실행
2. 로그 확인: `docker logs [container_name]`
3. 네트워크 확인: `docker network ls`
4. 강제 초기화: `docker system prune -f`