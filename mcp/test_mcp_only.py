#!/usr/bin/env python3
"""
MCP 서버만 테스트 (OpenAI API 키 없이)
"""

import json
import requests
import os
from typing import Dict, Any, Optional

# 설정
MCP_SERVER_URL = "http://localhost:9093"
DB_CONNECTION_ID = "upbit_analytics"

class UpbitMCPTest:
    def __init__(self, mcp_url: str):
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
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "query_upbit_analytics",
                    "arguments": {
                        "query": queries[function_name],
                        "params": params or []
                    }
                }
            }
            
            response = self.session.post(
                self.mcp_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ MCP query failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ MCP connection error: {e}")
            return None
    
    def test_functions(self):
        """MCP 함수들 테스트"""
        print("🔧 MCP 함수 테스트 시작")
        
        # 1. 코인 요약 테스트
        print("\n📊 get_coin_summary 테스트:")
        coin_data = self.get_mcp_data("coin_summary", ["KRW-BTC", 1])
        if coin_data:
            print(f"✅ 성공: {json.dumps(coin_data, indent=2, default=str)}")
        else:
            print("❌ 실패")
        
        # 2. 시장 움직임 테스트
        print("\n📈 get_market_movers 테스트:")
        market_data = self.get_mcp_data("market_movers", ["gainers", 5, 1])
        if market_data:
            print(f"✅ 성공: {json.dumps(market_data, indent=2, default=str)}")
        else:
            print("❌ 실패")
        
        # 3. 이상 거래 탐지 테스트
        print("\n⚡ detect_anomalies 테스트:")
        anomaly_data = self.get_mcp_data("detect_anomalies", [1, 3])
        if anomaly_data:
            print(f"✅ 성공: {json.dumps(anomaly_data, indent=2, default=str)}")
        else:
            print("❌ 실패")
        
        # 4. 시장 개요 테스트
        print("\n🌐 get_market_overview 테스트:")
        overview_data = self.get_mcp_data("market_overview")
        if overview_data:
            print(f"✅ 성공: {json.dumps(overview_data, indent=2, default=str)}")
        else:
            print("❌ 실패")

def main():
    print("🚀 Upbit MCP 서버 테스트 (OpenAI API 키 불필요)")
    print("=" * 60)
    
    # MCP 테스트 초기화
    mcp_test = UpbitMCPTest(MCP_SERVER_URL)
    
    # MCP 서버 상태 확인
    try:
        test_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "ping"
        }
        health_response = mcp_test.session.post(
            MCP_SERVER_URL,
            json=test_payload,
            headers={"Content-Type": "application/json"}
        )
        if health_response.status_code != 200:
            print("❌ MCP 서버가 실행되지 않았습니다.")
            print("   cd db-mcp-server && docker compose up -d")
            return
    except Exception as e:
        print(f"❌ MCP 서버에 연결할 수 없습니다: {e}")
        return
    
    print("✅ MCP 서버 연결 성공!")
    
    # 함수 테스트
    mcp_test.test_functions()
    
    print("\n🎉 MCP 서버 테스트 완료!")
    print("\n💡 다음 단계: OpenAI API 키 설정 후 LLM 연동 테스트")

if __name__ == "__main__":
    main()