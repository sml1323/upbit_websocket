#!/usr/bin/env python3
"""
Tool 기반 코인 Q&A 시스템 테스트
"""

import asyncio
import os
import sys
from pathlib import Path

# mvp-services 디렉토리를 path에 추가
sys.path.append(str(Path(__file__).parent / "mvp-services"))

from coin_qa_system import CoinQASystem
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

async def test_tool_based_qa():
    """Tool 기반 Q&A 시스템 테스트"""
    print("🚀 Tool 기반 코인 Q&A 시스템 테스트")
    print("=" * 60)
    
    qa_system = CoinQASystem()
    
    # 다양한 자연어 질의 테스트
    test_queries = [
        "비트코인 어떤 상황인가요?",
        "What's the current Bitcoin price?",
        "이더리움 분석해주세요",
        "Tell me about Ethereum trends",
        "XRP 투자해도 될까요?",
        "암호화폐 시장 전체 어떤가요?",
        "Which coins are available for analysis?"
    ]
    
    successful_tests = 0
    tool_calls_detected = 0
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n🔍 테스트 {i}: {query}")
        print("-" * 40)
        
        try:
            response = await qa_system.process_query(query)
            
            # Tool 호출 감지 확인 (로그에서)
            if "도구를 사용" in response or "분석" in response.lower():
                tool_calls_detected += 1
                print("✅ Tool 기반 응답 생성됨")
            
            print(f"📝 응답: {response[:200]}{'...' if len(response) > 200 else ''}")
            successful_tests += 1
            
        except Exception as e:
            print(f"❌ 오류: {e}")
        
        print()
    
    # 통계 출력
    stats = qa_system.get_stats()
    print("=" * 60)
    print("📊 테스트 결과:")
    print(f"• 총 질의: {len(test_queries)}")
    print(f"• 성공한 질의: {successful_tests}")
    print(f"• 성공률: {successful_tests/len(test_queries)*100:.1f}%")
    print(f"• Tool 호출 감지: {tool_calls_detected}회")
    print(f"• 시스템 성공률: {stats['success_rate']:.1f}%")
    print(f"• 인기 코인: {stats['top_coins'][:3]}")
    
    if successful_tests >= len(test_queries) * 0.8:
        print("\n🎉 테스트 성공! Tool 기반 시스템이 정상 작동합니다.")
    else:
        print("\n⚠️  테스트 부분 성공. 일부 개선이 필요합니다.")

if __name__ == "__main__":
    asyncio.run(test_tool_based_qa())