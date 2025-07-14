#!/usr/bin/env python3
"""
GPT-4o-mini + MCP 연동 테스트
Upbit LLM Analytics Platform
"""

import json
import requests
import os
from typing import Dict, Any, Optional
from openai import OpenAI

# 설정
MCP_SERVER_URL = "http://localhost:9092"
DB_CONNECTION_ID = "upbit_timescale"

class UpbitLLMAnalytics:
    def __init__(self, openai_api_key: str, mcp_url: str):
        self.client = OpenAI(api_key=openai_api_key)
        self.mcp_url = mcp_url
        self.session = requests.Session()
    
    def get_mcp_data(self, function_name: str, params: list = None) -> Optional[Dict[str, Any]]:
        """MCP 서버에서 데이터 가져오기"""
        try:
            # MCP 함수별 SQL 쿼리 매핑
            queries = {
                "coin_summary": "SELECT * FROM get_coin_summary($1, $2)",
                "market_movers": "SELECT * FROM get_market_movers($1, $2, $3)", 
                "detect_anomalies": "SELECT * FROM detect_anomalies($1, $2)",
                "market_overview": "SELECT * FROM get_market_overview()"
            }
            
            if function_name not in queries:
                return None
                
            payload = {
                "connection_id": DB_CONNECTION_ID,
                "query": queries[function_name],
                "params": params or []
            }
            
            response = self.session.post(
                f"{self.mcp_url}/v1/execute",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ MCP query failed: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ MCP connection error: {e}")
            return None
    
    def analyze_coin(self, coin_code: str) -> str:
        """특정 코인 분석"""
        print(f"📊 Analyzing {coin_code}...")
        
        # MCP에서 데이터 가져오기
        coin_data = self.get_mcp_data("coin_summary", [coin_code, 1])
        market_data = self.get_mcp_data("market_overview")
        
        if not coin_data or not market_data:
            return "❌ 데이터를 가져올 수 없습니다."
        
        # 토큰 최적화된 프롬프트 구성
        prompt = f"""
당신은 암호화폐 분석 전문가입니다. 다음 데이터를 바탕으로 {coin_code}에 대한 간결한 분석을 제공해주세요.

코인 데이터:
{json.dumps(coin_data, indent=2, default=str)}

시장 상황:
{json.dumps(market_data, indent=2, default=str)}

다음 형식으로 답변해주세요:
1. 현재 상태 (한 줄 요약)
2. 주요 시그널 (2-3개)
3. 투자 관점 (간단한 의견)

200단어 이내로 작성해주세요.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"❌ LLM 분석 실패: {e}"
    
    def market_overview_analysis(self) -> str:
        """전체 시장 분석"""
        print("🌐 Analyzing market overview...")
        
        # 다중 데이터 소스
        market_data = self.get_mcp_data("market_overview")
        top_gainers = self.get_mcp_data("market_movers", ["gainers", 5, 1])
        top_losers = self.get_mcp_data("market_movers", ["losers", 5, 1])
        anomalies = self.get_mcp_data("detect_anomalies", [1, 3])
        
        if not all([market_data, top_gainers, top_losers]):
            return "❌ 시장 데이터를 가져올 수 없습니다."
        
        prompt = f"""
암호화폐 시장 상황을 분석해주세요.

전체 시장:
{json.dumps(market_data, indent=2, default=str)}

상위 상승 코인:
{json.dumps(top_gainers, indent=2, default=str)}

상위 하락 코인:  
{json.dumps(top_losers, indent=2, default=str)}

이상 거래 탐지:
{json.dumps(anomalies, indent=2, default=str)}

다음 항목으로 분석해주세요:
1. 시장 전반 분위기
2. 주목할 만한 코인들
3. 이상 거래 패턴 해석
4. 향후 관전 포인트

300단어 이내로 작성해주세요.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"❌ 시장 분석 실패: {e}"
    
    def anomaly_alert_analysis(self) -> str:
        """이상 거래 알림 분석"""
        print("⚡ Analyzing anomalies...")
        
        anomalies = self.get_mcp_data("detect_anomalies", [1, 4])  # 높은 민감도
        
        if not anomalies:
            return "현재 특별한 이상 거래 패턴이 감지되지 않았습니다."
        
        prompt = f"""
다음 이상 거래 패턴을 분석하고 투자자들에게 알림을 제공해주세요.

이상 거래 데이터:
{json.dumps(anomalies, indent=2, default=str)}

다음 형식으로 답변해주세요:
1. 🚨 긴급도 (낮음/보통/높음/긴급)
2. 📊 주요 이상 패턴 요약
3. 💡 투자자 주의사항
4. 🔍 추가 모니터링 대상

150단어 이내로 간결하게 작성해주세요.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=250,
                temperature=0.5
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"❌ 이상 거래 분석 실패: {e}"

def main():
    print("🚀 Upbit LLM Analytics - GPT-4o-mini Integration Test")
    print("=" * 60)
    
    # OpenAI API 키 확인
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        print("   export OPENAI_API_KEY=your_api_key_here")
        return
    
    # LLM Analytics 초기화
    analytics = UpbitLLMAnalytics(openai_api_key, MCP_SERVER_URL)
    
    # MCP 서버 상태 확인
    try:
        health_response = analytics.session.get(f"{MCP_SERVER_URL}/health")
        if health_response.status_code != 200:
            print("❌ MCP 서버가 실행되지 않았습니다.")
            print("   cd mcp && ./start_mcp_server.sh")
            return
    except:
        print("❌ MCP 서버에 연결할 수 없습니다.")
        return
    
    print("✅ MCP 서버 연결 성공!")
    
    # 테스트 시나리오들
    print("\n" + "="*60)
    print("📊 테스트 1: 비트코인 분석")
    print("="*60)
    btc_analysis = analytics.analyze_coin("KRW-BTC")
    print(btc_analysis)
    
    print("\n" + "="*60)
    print("🌐 테스트 2: 전체 시장 분석")
    print("="*60)
    market_analysis = analytics.market_overview_analysis()
    print(market_analysis)
    
    print("\n" + "="*60)
    print("⚡ 테스트 3: 이상 거래 알림")
    print("="*60)
    anomaly_analysis = analytics.anomaly_alert_analysis()
    print(anomaly_analysis)
    
    print("\n" + "="*60)
    print("📊 테스트 4: 이더리움 분석")
    print("="*60)
    eth_analysis = analytics.analyze_coin("KRW-ETH")
    print(eth_analysis)
    
    print("\n🎉 LLM 연동 테스트 완료!")
    print("\n💡 성과 측정:")
    print("   ✅ 토큰 효율성: 원본 데이터 대신 계산된 지표만 사용")
    print("   ✅ 실시간 분석: MCP를 통한 즉시 데이터 접근") 
    print("   ✅ 다양한 시나리오: 코인별/시장별/이상거래 분석")
    print("\n🚀 다음 단계: 웹 인터페이스 구축 (Week 3-4)")

if __name__ == "__main__":
    main()