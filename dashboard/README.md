# Upbit LLM Analytics Dashboard

웹 기반 실시간 암호화폐 분석 대시보드

## 기능

### 1. 실시간 시장 요약
- WebSocket을 통한 5분 간격 시장 요약
- 알림 레벨별 색상 구분 (high/medium/low)
- 상승/하락/보합 코인 수 표시

### 2. 코인 Q&A 인터페이스
- 자연어 질문 입력 ("BTC 어때?", "이더리움 분석해줘")
- REST API를 통한 LLM 분석 결과
- 실시간 답변 표시

### 3. 이상 탐지 알림
- 거래량/가격 급변동 알림
- 심각도별 아이콘 표시 (🚨 critical, ⚠️ high, 📊 medium)
- 실시간 알림 업데이트

### 4. 기술적 지표 시각화
- RSI (Relative Strength Index) 표시
- 볼린저 밴드 분석
- 코인별 지표 선택 가능

### 5. 시장 통계
- 전체 시장 개요
- 상위 상승/하락 코인
- 최고 거래량 코인

## 사용법

### 1. 서버 시작
```bash
cd dashboard
python server.py --port 8000
```

### 2. 브라우저 접속
- **로컬**: http://localhost:8000
- **WSL**: http://172.31.65.200:8000

### 3. 사전 요구사항
다음 서비스들이 실행 중이어야 합니다:
```bash
# 모든 서비스 시작
docker-compose up -d

# 개별 서비스 확인
docker-compose ps
```

필요한 서비스:
- `mvp-market-summary`: WebSocket 서버 (포트 8765)
- `mvp-coin-qa`: HTTP API 서버 (포트 8080)
- `mcp-server`: MCP 서버 (포트 9093)
- `timescaledb`: 데이터베이스 (포트 5432)

## 기술 스택

### Frontend
- **HTML5 + CSS3**: 반응형 레이아웃
- **Bootstrap 5**: UI 컴포넌트
- **Font Awesome**: 아이콘
- **Chart.js**: 차트 라이브러리
- **WebSocket**: 실시간 통신

### Backend 연동
- **WebSocket**: 실시간 시장 요약 (`ws://localhost:8765`)
- **REST API**: 코인 Q&A (`http://localhost:8080/ask`)
- **MCP JSONRPC**: 기술적 지표 (`http://localhost:9093/jsonrpc`)

## 파일 구조

```
dashboard/
├── index.html          # 메인 대시보드 페이지
├── dashboard.js        # 대시보드 로직 (WebSocket, API 호출)
├── server.py           # 정적 파일 서버 (CORS 지원)
└── README.md           # 이 파일
```

## 주요 기능별 구현

### 1. 실시간 시장 요약
- `UpbitDashboard.connectWebSocket()`: WebSocket 연결
- `UpbitDashboard.updateMarketSummary()`: 시장 요약 업데이트
- 자동 재연결 기능 (최대 5회 시도)

### 2. 코인 Q&A
- `UpbitDashboard.askQuestion()`: 질문 전송
- POST /ask 엔드포인트 호출
- 로딩 스피너 및 오류 처리

### 3. 기술적 지표
- `UpbitDashboard.queryMCP()`: MCP 서버 쿼리
- RSI, 볼린저 밴드 데이터 로드
- 색상 기반 신호 표시

### 4. 이상 탐지
- `UpbitDashboard.loadAnomalyAlerts()`: 이상 탐지 로드
- 심각도별 알림 스타일링
- 5분마다 자동 업데이트

## 설정

### 포트 설정
- 대시보드 서버: 8000 (변경 가능)
- WebSocket 서버: 8765 (고정)
- API 서버: 8080 (고정)
- MCP 서버: 9093 (고정)

### CORS 설정
`server.py`에서 CORS 헤더 자동 추가:
```python
self.send_header('Access-Control-Allow-Origin', '*')
self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
self.send_header('Access-Control-Allow-Headers', 'Content-Type')
```

## 트러블슈팅

### 1. WebSocket 연결 실패
- `mvp-market-summary` 서비스 상태 확인
- 포트 8765 방화벽 확인

### 2. Q&A 응답 없음
- `mvp-coin-qa` 서비스 상태 확인
- OpenAI API 키 설정 확인

### 3. 기술적 지표 로드 실패
- `mcp-server` 서비스 상태 확인
- TimescaleDB 연결 확인

### 4. WSL 환경에서 접속 불가
- WSL IP 주소 확인: `ip addr show eth0`
- 올바른 IP로 접속 (예: http://172.31.65.200:8000)

## 개발 모드

개발 시 실시간 업데이트를 위해 브라우저 개발자 도구를 활용:
1. F12 → Console 탭에서 오류 확인
2. Network 탭에서 API 호출 상태 확인
3. WebSocket 연결 상태 모니터링

## 향후 개선사항

1. **차트 기능 강화**: 실시간 차트 업데이트
2. **알림 시스템**: 브라우저 알림 또는 이메일 알림
3. **커스터마이징**: 사용자별 설정 저장
4. **모바일 최적화**: 반응형 레이아웃 개선
5. **인증 시스템**: 사용자별 접근 제어