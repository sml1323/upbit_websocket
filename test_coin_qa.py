#!/usr/bin/env python3
"""
코인 질의응답 시스템 테스트
"""

import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor
from coin_qa_system import CoinQASystem
import os
from dotenv import load_dotenv

load_dotenv()

def test_db_connection():
    """DB 연결 테스트"""
    try:
        config = {
            'host': '127.0.0.1',  # IPv4 강제
            'port': 5432,
            'database': 'upbit_analytics',
            'user': 'upbit_user',
            'password': 'upbit_password'
        }
        
        with psycopg2.connect(**config) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT code, trade_price, change_rate FROM ticker_data ORDER BY time DESC LIMIT 5")
                results = cur.fetchall()
                print("✅ DB 연결 성공!")
                print("📊 최근 데이터:")
                for row in results:
                    print(f"  {row['code']}: {row['trade_price']:,.0f}원 ({row['change_rate']:+.2f}%)")
                return True
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")
        return False

def test_coin_code_mapping():
    """코인 코드 매핑 테스트"""
    from coin_qa_system import CoinCodeMapper
    
    mapper = CoinCodeMapper()
    
    test_queries = [
        "BTC 어때?",
        "비트코인 분석해줘",
        "bitcoin price",
        "KRW-BTC 상황은?",
        "W코인 어떤가요?",
        "잘못된 코인 ABC123"
    ]
    
    print("\n🔍 코인 코드 매핑 테스트:")
    for query in test_queries:
        coin_code = mapper.extract_coin_code(query)
        is_coin_query = mapper.is_coin_query(query)
        print(f"  '{query}' → {coin_code} (코인 질의: {is_coin_query})")

async def test_qa_system():
    """QA 시스템 테스트"""
    print("\n🤖 QA 시스템 테스트:")
    
    # DB 연결 설정 수정
    import coin_qa_system
    original_config = coin_qa_system.DatabaseManager.__init__
    
    def modified_init(self):
        self.config = {
            'host': '127.0.0.1',  # IPv4 강제
            'port': 5432,
            'database': 'upbit_analytics',
            'user': 'upbit_user',
            'password': 'upbit_password'
        }
    
    coin_qa_system.DatabaseManager.__init__ = modified_init
    
    qa_system = CoinQASystem()
    
    test_queries = [
        "BTC 어때?",
        "비트코인 분석해줘",
        "KRW-BTC 투자해도 될까?",
        "잘못된 질문",
        "존재하지 않는 코인 ABC123"
    ]
    
    for query in test_queries:
        print(f"\n❓ 질의: {query}")
        try:
            response = await qa_system.process_query(query)
            print(f"✅ 답변: {response}")
        except Exception as e:
            print(f"❌ 오류: {e}")

if __name__ == "__main__":
    print("🚀 코인 질의응답 시스템 테스트 시작!")
    print("=" * 50)
    
    # 1. DB 연결 테스트
    if test_db_connection():
        # 2. 코인 코드 매핑 테스트
        test_coin_code_mapping()
        
        # 3. QA 시스템 테스트
        asyncio.run(test_qa_system())
    
    print("\n🎉 테스트 완료!")