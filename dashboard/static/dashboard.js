// Upbit LLM Analytics Dashboard JavaScript
class UpbitDashboard {
    constructor() {
        this.websocket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.connectWebSocket();
        this.loadInitialData();
    }

    setupEventListeners() {
        // Q&A 버튼 이벤트
        document.getElementById('ask-button').addEventListener('click', () => {
            this.askQuestion();
        });

        // Q&A 입력 엔터 키 이벤트
        document.getElementById('coin-question').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.askQuestion();
            }
        });

        // 기술적 지표 로드 버튼
        document.getElementById('load-indicators').addEventListener('click', () => {
            this.loadTechnicalIndicators();
        });
    }

    // WebSocket 연결 (실시간 시장 요약)
    connectWebSocket() {
        const wsUrl = 'ws://localhost:8001/ws/market-summary';
        
        try {
            this.websocket = new WebSocket(wsUrl);

            this.websocket.onopen = (event) => {
                console.log('WebSocket 연결 성공');
                this.updateConnectionStatus(true);
                this.reconnectAttempts = 0;
            };

            this.websocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.updateMarketSummary(data);
            };

            this.websocket.onclose = (event) => {
                console.log('WebSocket 연결 종료');
                this.updateConnectionStatus(false);
                this.attemptReconnect();
            };

            this.websocket.onerror = (error) => {
                console.error('WebSocket 오류:', error);
                this.updateConnectionStatus(false);
            };

        } catch (error) {
            console.error('WebSocket 연결 실패:', error);
            this.updateConnectionStatus(false);
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`재연결 시도 ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
            
            setTimeout(() => {
                this.connectWebSocket();
            }, 3000 * this.reconnectAttempts);
        }
    }

    updateConnectionStatus(connected) {
        const statusIndicator = document.getElementById('connection-status');
        const statusText = document.getElementById('connection-text');

        if (connected) {
            statusIndicator.className = 'status-indicator status-connected';
            statusText.textContent = '연결됨';
        } else {
            statusIndicator.className = 'status-indicator status-disconnected';
            statusText.textContent = '연결 끊김';
        }
    }

    updateMarketSummary(data) {
        const content = document.getElementById('market-summary-content');
        const lastUpdate = document.getElementById('last-update');

        // 알림 레벨에 따른 스타일 적용
        const alertClass = `alert-level-${data.alert_level}`;
        content.className = `${alertClass}`;

        const alertIcon = data.alert_level === 'high' ? '🚨' : 
                         data.alert_level === 'medium' ? '⚠️' : '✅';

        content.innerHTML = `
            <div class="mb-3">
                <h6>${alertIcon} 알림 레벨: ${data.alert_level.toUpperCase()}</h6>
            </div>
            <div class="mb-3">
                <strong>시장 요약:</strong>
                <p class="mt-2">${data.summary_text}</p>
            </div>
            <div class="row text-center">
                <div class="col-3">
                    <div class="text-success">
                        <i class="fas fa-arrow-up"></i>
                        <div>${data.rising_coins}</div>
                        <small>상승</small>
                    </div>
                </div>
                <div class="col-3">
                    <div class="text-danger">
                        <i class="fas fa-arrow-down"></i>
                        <div>${data.falling_coins}</div>
                        <small>하락</small>
                    </div>
                </div>
                <div class="col-3">
                    <div class="text-muted">
                        <i class="fas fa-minus"></i>
                        <div>${data.neutral_coins}</div>
                        <small>보합</small>
                    </div>
                </div>
                <div class="col-3">
                    <div class="text-info">
                        <i class="fas fa-coins"></i>
                        <div>${data.total_coins}</div>
                        <small>전체</small>
                    </div>
                </div>
            </div>
        `;

        lastUpdate.textContent = new Date(data.timestamp).toLocaleString('ko-KR');
    }

    // 코인 Q&A 질문 처리
    async askQuestion() {
        const input = document.getElementById('coin-question');
        const responseDiv = document.getElementById('qa-response');
        const question = input.value.trim();

        if (!question) {
            return;
        }

        // 로딩 표시
        responseDiv.innerHTML = `
            <div class="loading">
                <div class="spinner-border spinner-border-sm" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <span class="ms-2">분석 중...</span>
            </div>
        `;

        try {
            const response = await fetch('/api/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ question: question })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            responseDiv.innerHTML = `
                <div class="mb-2">
                    <strong>질문:</strong> ${question}
                </div>
                <div class="mb-2">
                    <strong>답변:</strong>
                </div>
                <div class="text-light">
                    ${data.answer.replace(/\n/g, '<br>')}
                </div>
            `;

            input.value = '';

        } catch (error) {
            console.error('Q&A 요청 실패:', error);
            responseDiv.innerHTML = `
                <div class="text-danger">
                    <i class="fas fa-exclamation-triangle"></i>
                    질문 처리 중 오류가 발생했습니다.
                </div>
            `;
        }
    }

    // 기술적 지표 로드
    async loadTechnicalIndicators() {
        const coinSelector = document.getElementById('coin-selector');
        const indicatorsContent = document.getElementById('indicators-content');
        const selectedCoin = coinSelector.value;

        indicatorsContent.innerHTML = `
            <div class="loading">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div class="mt-2">기술적 지표 로딩 중...</div>
            </div>
        `;

        try {
            // RSI 데이터 로드
            const rsiResponse = await this.queryMCP('calculate_rsi', { coin_code: selectedCoin });
            const bbResponse = await this.queryMCP('calculate_bollinger_bands', { coin_code: selectedCoin });

            indicatorsContent.innerHTML = `
                <div class="row">
                    <div class="col-md-6">
                        <h6><i class="fas fa-chart-line me-2"></i>RSI</h6>
                        <div class="bg-dark p-3 rounded">
                            <div class="text-center">
                                <div class="display-4 ${this.getRSIColor(rsiResponse.rsi_value)}">${rsiResponse.rsi_value}</div>
                                <small class="text-muted">RSI 값</small>
                            </div>
                            <div class="mt-2">
                                <div class="text-${this.getRSIColor(rsiResponse.rsi_value)}">
                                    ${rsiResponse.signal}
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <h6><i class="fas fa-chart-area me-2"></i>볼린저 밴드</h6>
                        <div class="bg-dark p-3 rounded">
                            <div class="small mb-2">
                                <div>상한선: ${bbResponse.upper_band}</div>
                                <div>중간선: ${bbResponse.middle_band}</div>
                                <div>하한선: ${bbResponse.lower_band}</div>
                            </div>
                            <div class="text-${this.getBBColor(bbResponse.signal)}">
                                ${bbResponse.signal}
                            </div>
                        </div>
                    </div>
                </div>
            `;

        } catch (error) {
            console.error('기술적 지표 로드 실패:', error);
            indicatorsContent.innerHTML = `
                <div class="text-danger text-center">
                    <i class="fas fa-exclamation-triangle"></i>
                    <div class="mt-2">기술적 지표 로드 실패</div>
                </div>
            `;
        }
    }

    // MCP 쿼리 실행
    async queryMCP(functionName, args) {
        const payload = {
            jsonrpc: "2.0",
            method: "tools/call",
            params: {
                name: functionName,
                arguments: args
            },
            id: 1
        };

        const response = await fetch('/api/mcp', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`MCP query failed: ${response.status}`);
        }

        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error.message);
        }

        // MCP 응답에서 실제 데이터 추출
        const content = data.result.content[0].text;
        return JSON.parse(content);
    }

    getRSIColor(rsiValue) {
        if (rsiValue >= 70) return 'danger';
        if (rsiValue <= 30) return 'success';
        return 'warning';
    }

    getBBColor(signal) {
        if (signal.includes('상승')) return 'success';
        if (signal.includes('하락')) return 'danger';
        return 'warning';
    }

    // 초기 데이터 로드
    loadInitialData() {
        // 시장 통계 로드
        this.loadMarketStats();
        
        // 이상 탐지 알림 로드
        this.loadAnomalyAlerts();
    }

    async loadMarketStats() {
        const statsDiv = document.getElementById('market-stats');
        
        try {
            const response = await this.queryMCP('get_market_overview', {});
            
            statsDiv.innerHTML = `
                <div class="row text-center">
                    <div class="col-md-3 mb-3">
                        <div class="card bg-success">
                            <div class="card-body">
                                <h5>${response.rising_coins}</h5>
                                <small>상승 코인</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3 mb-3">
                        <div class="card bg-danger">
                            <div class="card-body">
                                <h5>${response.falling_coins}</h5>
                                <small>하락 코인</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3 mb-3">
                        <div class="card bg-warning">
                            <div class="card-body">
                                <h5>${response.top_gainer}</h5>
                                <small>최고 상승</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3 mb-3">
                        <div class="card bg-info">
                            <div class="card-body">
                                <h5>${response.highest_volume}</h5>
                                <small>최고 거래량</small>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } catch (error) {
            console.error('시장 통계 로드 실패:', error);
            statsDiv.innerHTML = `
                <div class="text-danger text-center">
                    시장 통계 로드 실패
                </div>
            `;
        }
    }

    async loadAnomalyAlerts() {
        const alertsDiv = document.getElementById('anomaly-alerts');
        
        try {
            const response = await this.queryMCP('detect_anomalies', { timeframe_hours: 1, sensitivity: 3 });
            
            if (response.length === 0) {
                alertsDiv.innerHTML = `
                    <div class="text-success text-center">
                        <i class="fas fa-check-circle"></i>
                        <div class="mt-2">이상 거래 없음</div>
                    </div>
                `;
                return;
            }

            let alertsHtml = '';
            response.forEach(alert => {
                const severityIcon = alert.severity === 'critical' ? '🚨' : 
                                   alert.severity === 'high' ? '⚠️' : '📊';
                const severityColor = alert.severity === 'critical' ? 'danger' : 
                                    alert.severity === 'high' ? 'warning' : 'info';

                alertsHtml += `
                    <div class="alert alert-${severityColor} alert-dismissible fade show" role="alert">
                        <div class="d-flex align-items-center">
                            <span class="me-2">${severityIcon}</span>
                            <div>
                                <strong>${alert.code}</strong>
                                <div class="small">${alert.description}</div>
                            </div>
                        </div>
                    </div>
                `;
            });

            alertsDiv.innerHTML = alertsHtml;

        } catch (error) {
            console.error('이상 탐지 로드 실패:', error);
            alertsDiv.innerHTML = `
                <div class="text-danger text-center">
                    이상 탐지 로드 실패
                </div>
            `;
        }
    }
}

// 대시보드 초기화
document.addEventListener('DOMContentLoaded', () => {
    new UpbitDashboard();
});

// 주기적으로 데이터 업데이트 (5분마다)
setInterval(() => {
    const dashboard = new UpbitDashboard();
    dashboard.loadMarketStats();
    dashboard.loadAnomalyAlerts();
}, 5 * 60 * 1000);