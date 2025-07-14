#!/usr/bin/env python3
"""
Test MCP Server connection to TimescaleDB
"""
import requests
import json

def test_mcp_server():
    """Test MCP server functionality"""
    print("🧪 Testing MCP Server connection to TimescaleDB...")
    
    # Test 1: Health check
    print("\n1. Health Check")
    try:
        response = requests.get("http://localhost:9093/status")
        print(f"✅ Status: {response.json()}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
    
    # Test 2: List databases
    print("\n2. List Databases")
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "list_databases",
                "arguments": {}
            },
            "id": 1
        }
        response = requests.post("http://localhost:9093/jsonrpc", json=payload)
        result = response.json()
        print(f"✅ Databases: {result}")
    except Exception as e:
        print(f"❌ List databases failed: {e}")
    
    # Test 3: Schema info
    print("\n3. Database Schema")
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "schema_upbit_analytics",
                "arguments": {}
            },
            "id": 2
        }
        response = requests.post("http://localhost:9093/jsonrpc", json=payload)
        result = response.json()
        print(f"✅ Schema info received: {len(str(result))} characters")
    except Exception as e:
        print(f"❌ Schema query failed: {e}")
    
    # Test 4: Query ticker data
    print("\n4. Query Ticker Data")
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "query_upbit_analytics",
                "arguments": {
                    "query": "SELECT code, trade_price, trade_volume, time FROM ticker_data ORDER BY time DESC LIMIT 5"
                }
            },
            "id": 3
        }
        response = requests.post("http://localhost:9093/jsonrpc", json=payload)
        result = response.json()
        print(f"✅ Query result: {result}")
    except Exception as e:
        print(f"❌ Ticker data query failed: {e}")
    
    # Test 5: Query continuous aggregates
    print("\n5. Query Continuous Aggregates")
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "query_upbit_analytics",
                "arguments": {
                    "query": "SELECT bucket, code, open, high, low, close, volume FROM ohlcv_1m ORDER BY bucket DESC LIMIT 3"
                }
            },
            "id": 4
        }
        response = requests.post("http://localhost:9093/jsonrpc", json=payload)
        result = response.json()
        print(f"✅ OHLCV data: {result}")
    except Exception as e:
        print(f"❌ OHLCV query failed: {e}")
    
    print("\n🎉 MCP Server test completed!")
    return True

if __name__ == "__main__":
    test_mcp_server()