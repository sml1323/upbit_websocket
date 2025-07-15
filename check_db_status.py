#!/usr/bin/env python3
"""
Check TimescaleDB status via MCP Server
"""
import requests
import json

def mcp_query(query, description=""):
    """Execute a query via MCP server"""
    print(f"\n📊 {description}")
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "query_upbit_timescaledb",
                "arguments": {
                    "query": query
                }
            },
            "id": 1
        }
        response = requests.post("http://localhost:9093/jsonrpc", json=payload)
        result = response.json()
        
        if 'result' in result and 'content' in result['result']:
            for content in result['result']['content']:
                if content['type'] == 'text':
                    print(content['text'])
        else:
            print(f"Result: {result}")
            
    except Exception as e:
        print(f"❌ Query failed: {e}")

def test_mcp_function(function_name, args, description=""):
    """Test MCP function"""
    print(f"\n🔧 {description}")
    try:
        payload = {
            "jsonrpc": "2.0", 
            "method": "tools/call",
            "params": {
                "name": function_name,
                "arguments": args
            },
            "id": 1
        }
        response = requests.post("http://localhost:9093/jsonrpc", json=payload)
        result = response.json()
        
        if 'result' in result and 'content' in result['result']:
            for content in result['result']['content']:
                if content['type'] == 'text':
                    print(content['text'])
        else:
            print(f"Result: {result}")
            
    except Exception as e:
        print(f"❌ Function test failed: {e}")

def main():
    print("🔍 TimescaleDB 상태 확인 (MCP 서버 경유)")
    
    # 1. 테이블 구조 확인
    mcp_query(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'ticker_data' ORDER BY ordinal_position",
        "1. ticker_data 테이블 구조 확인"
    )
    
    # 2. 최근 데이터 확인  
    mcp_query(
        "SELECT * FROM ticker_data ORDER BY time DESC LIMIT 5",
        "2. 최근 데이터 확인 (최근 5개 레코드)"
    )
    
    # 3. 사용 가능한 코인 확인
    mcp_query(
        "SELECT DISTINCT code FROM ticker_data WHERE time >= NOW() - INTERVAL '1 day' ORDER BY code LIMIT 10",
        "3. 사용 가능한 코인 확인 (최근 1일 기준, 처음 10개)"
    )
    
    # 4. 전체 데이터 통계
    mcp_query(
        "SELECT COUNT(*) as total_records, COUNT(DISTINCT code) as unique_coins, MIN(time) as earliest_data, MAX(time) as latest_data FROM ticker_data",
        "4. 전체 데이터 통계"
    )
    
    # 5. 스키마 정보 확인
    test_mcp_function(
        "schema_upbit_timescaledb",
        {},
        "5. 데이터베이스 스키마 정보 확인"
    )
    
    # 6. 연속 집계 테이블 확인
    mcp_query(
        "SELECT bucket, code, open, high, low, close, volume FROM ohlcv_1m WHERE code = 'KRW-BTC' ORDER BY bucket DESC LIMIT 5",
        "6. OHLCV 1분 집계 데이터 확인 (BTC)"
    )
    
    print("\n✅ 데이터베이스 상태 확인 완료!")

if __name__ == "__main__":
    main()