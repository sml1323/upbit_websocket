// Upbit LLM Analytics Dashboard JavaScript
// WebSocket 및 API 연동 스크립트

class DashboardManager {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectInterval = 5000; // 5초
    }

    // WebSocket 연결 관리
    connectWebSocket() {
        if (this.isConnected) {
            this.disconnectWebSocket();
            return;
        }

        console.log('WebSocket 연결 시도...');
        this.updateConnectionStatus('연결 중...');

        try {
            this.ws = new WebSocket('ws://localhost:8001/ws/market-summary');

            this.ws.onopen = (event) => {
                console.log('WebSocket 연결됨');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('연결됨', 'success');
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMarketData(data);
                } catch (error) {
                    console.error('데이터 파싱 오류:', error);
                    this.displayError('데이터 파싱 오류');
                }
            };

            this.ws.onclose = (event) => {
                console.log('WebSocket 연결 종료');
                this.isConnected = false;
                this.updateConnectionStatus('연결 종료', 'warning');
                
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    setTimeout(() => this.attemptReconnect(), this.reconnectInterval);
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket 오류:', error);
                this.isConnected = false;
                this.updateConnectionStatus('연결 실패', 'error');
            };

        } catch (error) {
            console.error('WebSocket 생성 오류:', error);
            this.updateConnectionStatus('연결 실패', 'error');
        }
    }

    // 자동 재연결
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.updateConnectionStatus('재연결 실패', 'error');
            return;
        }

        this.reconnectAttempts++;
        console.log(`재연결 시도 ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
        this.updateConnectionStatus(`재연결 중... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`, 'warning');
        this.connectWebSocket();
    }

    // WebSocket 연결 해제
    disconnectWebSocket() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.isConnected = false;
        this.updateConnectionStatus('연결 해제', 'info');
    }

    // 연결 상태 UI 업데이트
    updateConnectionStatus(message, type = 'info') {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            statusElement.textContent = message;
            statusElement.className = `status ${type}`;
        }
    }

    // 시장 데이터 처리
    handleMarketData(data) {
        console.log('시장 데이터 수신:', data);
        
        const timestamp = new Date().toLocaleString('ko-KR');
        const marketSummaryDiv = document.getElementById('market-data');
        
        if (!marketSummaryDiv) return;

        let html = `<div class="market-update">
            <div class="timestamp">${timestamp}</div>`;

        if (data.market_summary) {
            html += `<div class="summary">${data.market_summary}</div>`;
        }

        if (data.top_gainers && data.top_gainers.length > 0) {
            html += `<div class="gainers">
                <strong>📈 상승:</strong> 
                ${data.top_gainers.map(coin => 
                    `<span class="coin positive">${coin.market} +${coin.change_rate}%</span>`
                ).join(' ')}
            </div>`;
        }

        if (data.top_losers && data.top_losers.length > 0) {
            html += `<div class="losers">
                <strong>📉 하락:</strong> 
                ${data.top_losers.map(coin => 
                    `<span class="coin negative">${coin.market} ${coin.change_rate}%</span>`
                ).join(' ')}
            </div>`;
        }

        html += `</div>`;

        // 새 데이터를 상단에 추가
        marketSummaryDiv.innerHTML = html + marketSummaryDiv.innerHTML;

        // 최대 10개 업데이트만 유지
        const updates = marketSummaryDiv.children;
        while (updates.length > 10) {
            marketSummaryDiv.removeChild(updates[updates.length - 1]);
        }
    }

    // 오류 메시지 표시
    displayError(message) {
        const errorDiv = document.getElementById('error-messages');
        if (errorDiv) {
            const timestamp = new Date().toLocaleString('ko-KR');
            errorDiv.innerHTML = `<div class="error-message">
                <span class="error-time">${timestamp}</span>
                <span class="error-text">${message}</span>
            </div>` + errorDiv.innerHTML;
        }
    }

    // API 서비스 상태 확인
    async checkServiceStatus() {
        const services = [
            { name: 'Dashboard', url: '/health', element: 'dashboard-status' },
            { name: 'Coin Q&A', url: 'http://localhost:8080/health', element: 'qa-status' },
            { name: 'Market Summary', url: 'http://localhost:8765', element: 'market-status' }
        ];

        for (const service of services) {
            try {
                const response = await fetch(service.url, { 
                    method: 'GET',
                    timeout: 5000
                });
                
                const statusElement = document.getElementById(service.element);
                if (statusElement) {
                    if (response.ok) {
                        statusElement.className = 'status-indicator online';
                        statusElement.title = `${service.name} 서비스 정상`;
                    } else {
                        statusElement.className = 'status-indicator warning';
                        statusElement.title = `${service.name} 서비스 응답 이상`;
                    }
                }
            } catch (error) {
                console.log(`${service.name} 서비스 확인 실패:`, error);
                const statusElement = document.getElementById(service.element);
                if (statusElement) {
                    statusElement.className = 'status-indicator offline';
                    statusElement.title = `${service.name} 서비스 연결 불가`;
                }
            }
        }
    }

    // API 데이터 가져오기
    async fetchApiData(endpoint) {
        try {
            const response = await fetch(endpoint);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error(`API 요청 실패 (${endpoint}):`, error);
            this.displayError(`API 요청 실패: ${endpoint}`);
            return null;
        }
    }

    // 대시보드 초기화
    async initialize() {
        console.log('대시보드 초기화 중...');
        
        // 서비스 상태 확인
        await this.checkServiceStatus();
        
        // 주기적 상태 확인 (30초마다)
        setInterval(() => this.checkServiceStatus(), 30000);
        
        // 이벤트 리스너 설정
        this.setupEventListeners();
        
        console.log('대시보드 초기화 완료');
    }

    // 이벤트 리스너 설정
    setupEventListeners() {
        // WebSocket 연결 버튼
        const connectBtn = document.getElementById('connect-websocket');
        if (connectBtn) {
            connectBtn.addEventListener('click', () => this.connectWebSocket());
        }

        // 새로고침 버튼
        const refreshBtn = document.getElementById('refresh-data');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.checkServiceStatus();
                window.location.reload();
            });
        }
    }
}

// 전역 대시보드 인스턴스
let dashboard = null;

// DOM 로드 완료 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    dashboard = new DashboardManager();
    dashboard.initialize();
});

// 창 닫기 시 WebSocket 정리
window.addEventListener('beforeunload', function() {
    if (dashboard && dashboard.ws) {
        dashboard.disconnectWebSocket();
    }
});