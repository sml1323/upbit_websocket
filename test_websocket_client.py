#!/usr/bin/env python3
"""
MVP 실시간 시장 요약 WebSocket 클라이언트 테스트
"""
import asyncio
import websockets
import json

async def test_market_summary():
    uri = "ws://localhost:8765"
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket 연결 성공!")
            
            # 연결 후 첫 번째 메시지 받기
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(message)
                print("📊 시장 요약 데이터 수신:")
                print(f"  - 타임스탬프: {data.get('timestamp')}")
                print(f"  - 상위 코인 수: {len(data.get('top_coins', []))}")
                print(f"  - 시장 무버스: {len(data.get('market_movers', []))}")
                print(f"  - LLM 분석: {data.get('llm_analysis', 'N/A')[:100]}...")
                return True
            except asyncio.TimeoutError:
                print("⚠️  10초 내 데이터 수신 실패")
                return False
                
    except Exception as e:
        print(f"❌ WebSocket 연결 실패: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_market_summary())
    exit(0 if success else 1)