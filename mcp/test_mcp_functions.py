#!/usr/bin/env python3
"""
MCP 함수 테스트 스크립트
FreePeak db-mcp-server를 통해 우리의 핵심 함수들을 테스트
"""

import os
import json
import requests
import time
from typing import Dict, Any, Optional

# MCP 서버 설정
MCP_SERVER_URL = "http://localhost:9092"
DB_CONNECTION_ID = "upbit_timescale"

class MCPTester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        
    def health_check(self) -> bool:
        """MCP 서버 상태 확인"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False
    
    def execute_query(self, sql: str, params: list = None) -> Optional[Dict[str, Any]]:
        """SQL 쿼리 실행"""
        try:
            payload = {
                "connection_id": DB_CONNECTION_ID,
                "query": sql,
                "params": params or []
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/execute",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Query failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Query execution error: {e}")
            return None
    
    def test_coin_summary(self, code: str = "KRW-BTC") -> None:
        """get_coin_summary 함수 테스트"""
        print(f"\n📊 Testing get_coin_summary for {code}...")
        
        sql = "SELECT * FROM get_coin_summary($1, $2)"
        params = [code, 1]  # 1시간 timeframe
        
        result = self.execute_query(sql, params)
        if result:
            print("✅ get_coin_summary result:")
            print(json.dumps(result, indent=2, default=str))
        else:
            print("❌ get_coin_summary failed")
    
    def test_market_movers(self, move_type: str = "gainers") -> None:
        """get_market_movers 함수 테스트"""
        print(f"\n🔥 Testing get_market_movers ({move_type})...")
        
        sql = "SELECT * FROM get_market_movers($1, $2, $3)"
        params = [move_type, 5, 1]  # 상위 5개, 1시간
        
        result = self.execute_query(sql, params)
        if result:
            print("✅ get_market_movers result:")
            print(json.dumps(result, indent=2, default=str))
        else:
            print("❌ get_market_movers failed")
    
    def test_detect_anomalies(self, sensitivity: int = 3) -> None:
        """detect_anomalies 함수 테스트"""
        print(f"\n⚡ Testing detect_anomalies (sensitivity: {sensitivity})...")
        
        sql = "SELECT * FROM detect_anomalies($1, $2)"
        params = [1, sensitivity]  # 1시간, 민감도
        
        result = self.execute_query(sql, params)
        if result:
            print("✅ detect_anomalies result:")
            print(json.dumps(result, indent=2, default=str))
        else:
            print("❌ detect_anomalies failed")
    
    def test_market_overview(self) -> None:
        """get_market_overview 함수 테스트"""
        print(f"\n🌐 Testing get_market_overview...")
        
        sql = "SELECT * FROM get_market_overview()"
        
        result = self.execute_query(sql)
        if result:
            print("✅ get_market_overview result:")
            print(json.dumps(result, indent=2, default=str))
        else:
            print("❌ get_market_overview failed")
    
    def test_basic_connection(self) -> None:
        """기본 연결 테스트"""
        print("\n🔍 Testing basic database connection...")
        
        # 간단한 쿼리로 연결 확인
        sql = "SELECT COUNT(*) as total_records FROM ticker_data WHERE time >= NOW() - INTERVAL '1 hour'"
        
        result = self.execute_query(sql)
        if result:
            print("✅ Database connection successful:")
            print(json.dumps(result, indent=2, default=str))
        else:
            print("❌ Database connection failed")

def main():
    print("🚀 Upbit LLM Analytics - MCP Functions Test")
    print("=" * 50)
    
    # MCP 테스터 초기화
    tester = MCPTester(MCP_SERVER_URL)
    
    # 1. Health check
    print("🏥 Checking MCP server health...")
    if not tester.health_check():
        print("❌ MCP server is not running. Please start it first:")
        print("   cd mcp && ./start_mcp_server.sh")
        return
    
    print("✅ MCP server is healthy!")
    
    # 2. 기본 연결 테스트
    tester.test_basic_connection()
    
    # 3. 핵심 MCP 함수들 테스트
    tester.test_coin_summary("KRW-BTC")
    tester.test_market_movers("gainers")
    tester.test_detect_anomalies(3)
    tester.test_market_overview()
    
    # 4. 다른 케이스들 테스트
    print("\n🔄 Testing additional cases...")
    tester.test_coin_summary("KRW-ETH")
    tester.test_market_movers("losers")
    tester.test_detect_anomalies(5)  # 높은 민감도
    
    print("\n🎉 MCP function testing completed!")
    print("\n💡 Next steps:")
    print("   1. If tests pass → Start LLM integration")
    print("   2. If tests fail → Check database schema and data")
    print("   3. Monitor MCP server logs: docker logs upbit-mcp-server")

if __name__ == "__main__":
    main()