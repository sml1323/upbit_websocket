#!/usr/bin/env python3
"""
코인별 질의응답 시스템
- 자연어 질의 처리 ("W코인 어때?" → 코인 분석)
- LLM 프롬프트 최적화 (정확하고 간결한 답변)
- 질의 패턴 분석 및 최적화
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI
from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# OpenAI 클라이언트 초기화
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

@dataclass
class CoinAnalysis:
    """코인 분석 결과"""
    coin_code: str
    current_price: float
    change_rate: float
    trend: str
    volume_spike: bool
    support_level: float
    resistance_level: float
    volatility: str
    market_cap_rank: str
    analysis_text: str
    confidence: float
    timestamp: str

class CoinCodeMapper:
    """코인 코드 매핑 및 인식"""
    
    def __init__(self):
        # 일반적인 코인 별명 매핑
        self.coin_aliases = {
            # 비트코인
            'bitcoin': 'KRW-BTC',
            'btc': 'KRW-BTC',
            'bitcoin': 'KRW-BTC',
            '비트코인': 'KRW-BTC',
            '비트': 'KRW-BTC',
            
            # 이더리움
            'ethereum': 'KRW-ETH',
            'eth': 'KRW-ETH',
            'ether': 'KRW-ETH',
            '이더리움': 'KRW-ETH',
            '이더': 'KRW-ETH',
            
            # 리플
            'ripple': 'KRW-XRP',
            'xrp': 'KRW-XRP',
            '리플': 'KRW-XRP',
            
            # 기타 주요 코인들
            'dogecoin': 'KRW-DOGE',
            'doge': 'KRW-DOGE',
            '도지코인': 'KRW-DOGE',
            '도지': 'KRW-DOGE',
            
            'ada': 'KRW-ADA',
            'cardano': 'KRW-ADA',
            '카르다노': 'KRW-ADA',
            '에이다': 'KRW-ADA',
            
            'solana': 'KRW-SOL',
            'sol': 'KRW-SOL',
            '솔라나': 'KRW-SOL',
            '솔': 'KRW-SOL',
            
            # W코인 (예시)
            'w코인': 'KRW-W',
            'w': 'KRW-W',
            'wcoin': 'KRW-W',
        }
        
        # 정규표현식 패턴
        self.patterns = [
            r'KRW-([A-Z0-9]+)',  # KRW-BTC 형태
            r'([A-Z0-9]+)코인',   # BTC코인 형태
            r'([A-Z0-9]+)',       # BTC 형태
        ]
    
    def extract_coin_code(self, query: str) -> Optional[str]:
        """쿼리에서 코인 코드 추출"""
        query_lower = query.lower().strip()
        
        # 1. 직접 별명 매핑 확인
        for alias, code in self.coin_aliases.items():
            if alias in query_lower:
                return code
        
        # 2. 정규표현식 패턴 매칭
        for pattern in self.patterns:
            match = re.search(pattern, query.upper())
            if match:
                if pattern.startswith('KRW-'):
                    return match.group(0)
                else:
                    return f"KRW-{match.group(1)}"
        
        return None
    
    def is_coin_query(self, query: str) -> bool:
        """코인 관련 질의인지 판단"""
        coin_keywords = [
            '코인', '어때', '분석', '가격', '추천', '전망', '매수', '매도',
            '상승', '하락', '투자', '수익', '손실', '차트', '기술적',
            'price', 'coin', 'crypto', 'analysis', 'buy', 'sell'
        ]
        
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in coin_keywords)

class DatabaseManager:
    """TimescaleDB 연결 및 쿼리 관리"""
    
    def __init__(self):
        self.config = {
            'host': os.getenv('TIMESCALEDB_HOST', 'localhost'),
            'port': int(os.getenv('TIMESCALEDB_PORT', '5432')),
            'database': os.getenv('TIMESCALEDB_DBNAME', 'upbit_analytics'),
            'user': os.getenv('TIMESCALEDB_USER', 'upbit_user'),
            'password': os.getenv('TIMESCALEDB_PASSWORD', 'upbit_password')
        }
        
    def get_connection(self):
        """DB 연결 생성"""
        return psycopg2.connect(**self.config)
    
    def get_coin_summary(self, coin_code: str, timeframe_hours: int = 24) -> Optional[Dict]:
        """특정 코인의 요약 정보 조회"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM get_coin_summary(%s, %s)",
                        (coin_code, timeframe_hours)
                    )
                    result = cur.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            logger.error(f"코인 요약 조회 실패 ({coin_code}): {e}")
            return None
    
    def get_coin_history(self, coin_code: str, hours: int = 24) -> List[Dict]:
        """코인 가격 히스토리 조회"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            time, trade_price, trade_volume, change_rate
                        FROM ticker_data
                        WHERE code = %s 
                          AND time >= NOW() - INTERVAL '%s hours'
                        ORDER BY time DESC
                        LIMIT 100
                    """, (coin_code, hours))
                    
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"코인 히스토리 조회 실패 ({coin_code}): {e}")
            return []
    
    def get_available_coins(self) -> List[str]:
        """사용 가능한 코인 목록 조회"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT DISTINCT code 
                        FROM ticker_data 
                        WHERE time >= NOW() - INTERVAL '1 day'
                        ORDER BY code
                    """)
                    return [row[0] for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"코인 목록 조회 실패: {e}")
            return []

class LLMAnalyzer:
    """LLM 기반 코인 분석기 (Tool-based)"""
    
    def __init__(self):
        self.model = "gpt-4o-mini"  # 비용 효율적인 모델 사용
        self.tools = self._define_tools()
    
    def _define_tools(self):
        """OpenAI Tools 정의"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_cryptocurrency_analysis",
                    "description": "Get detailed analysis of a specific cryptocurrency including current price, trends, volume, and market data. Call this when users ask about any cryptocurrency analysis, price, or trends.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "cryptocurrency_symbol": {
                                "type": "string",
                                "description": "Cryptocurrency symbol or name in various formats (e.g., BTC, Bitcoin, 비트코인, ETH, Ethereum, XRP, Ripple, etc.)"
                            },
                            "timeframe_hours": {
                                "type": "integer",
                                "description": "Analysis timeframe in hours (default: 24)",
                                "default": 24
                            }
                        },
                        "required": ["cryptocurrency_symbol"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "get_cryptocurrency_price_history",
                    "description": "Get price and volume history for a specific cryptocurrency. Use this for trend analysis and historical data queries.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "cryptocurrency_symbol": {
                                "type": "string",
                                "description": "Cryptocurrency symbol or name in various formats"
                            },
                            "hours": {
                                "type": "integer", 
                                "description": "Hours of historical data to retrieve (default: 24)",
                                "default": 24
                            }
                        },
                        "required": ["cryptocurrency_symbol"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_available_cryptocurrencies", 
                    "description": "Get list of all available cryptocurrencies for analysis. Use this when users ask about supported coins or want to see what's available.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False
                    }
                }
            }
        ]
    
    def handle_tool_call(self, tool_call, db_manager: DatabaseManager, code_mapper: CoinCodeMapper):
        """Tool 호출 처리"""
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        
        try:
            if function_name == "get_cryptocurrency_analysis":
                crypto_symbol = arguments["cryptocurrency_symbol"]
                timeframe_hours = arguments.get("timeframe_hours", 24)
                
                # 코인 코드 변환 (BTC → KRW-BTC)
                coin_code = code_mapper.extract_coin_code(crypto_symbol)
                if not coin_code:
                    return {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": json.dumps({
                            "error": f"Cryptocurrency '{crypto_symbol}' not found or not supported"
                        })
                    }
                
                # 코인 데이터 조회
                coin_data = db_manager.get_coin_summary(coin_code, timeframe_hours)
                if not coin_data:
                    return {
                        "tool_call_id": tool_call.id,
                        "role": "tool", 
                        "content": json.dumps({
                            "error": f"No data available for {crypto_symbol} ({coin_code})"
                        })
                    }
                
                return {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": json.dumps({
                        "coin_code": coin_code,
                        "symbol": crypto_symbol,
                        "current_price": float(coin_data.get("current_price", 0)) if coin_data.get("current_price") else None,
                        "change_rate": float(coin_data.get("change_rate", 0)) if coin_data.get("change_rate") else None, 
                        "trend": str(coin_data.get("trend", "")),
                        "volume_spike": bool(coin_data.get("volume_spike", False)),
                        "volatility": str(coin_data.get("volatility", "")),
                        "support_level": float(coin_data.get("support_level", 0)) if coin_data.get("support_level") else None,
                        "resistance_level": float(coin_data.get("resistance_level", 0)) if coin_data.get("resistance_level") else None,
                        "analysis_summary": str(coin_data.get("analysis_summary", "No summary available")),
                        "timeframe_hours": timeframe_hours
                    })
                }
                
            elif function_name == "get_cryptocurrency_price_history":
                crypto_symbol = arguments["cryptocurrency_symbol"]
                hours = arguments.get("hours", 24)
                
                # 코인 코드 변환
                coin_code = code_mapper.extract_coin_code(crypto_symbol)
                if not coin_code:
                    return {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": json.dumps({
                            "error": f"Cryptocurrency '{crypto_symbol}' not found"
                        })
                    }
                
                # 히스토리 데이터 조회
                history = db_manager.get_coin_history(coin_code, hours)
                if not history:
                    return {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": json.dumps({
                            "error": f"No historical data available for {crypto_symbol}"
                        })
                    }
                
                # 최근 10개 데이터만 전송 (토큰 절약)
                recent_history = history[:10]
                formatted_history = [
                    {
                        "time": str(h["time"]),
                        "price": float(h["trade_price"]),
                        "volume": float(h["trade_volume"]),
                        "change_rate": float(h.get("change_rate", 0))
                    }
                    for h in recent_history
                ]
                
                return {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": json.dumps({
                        "coin_code": coin_code,
                        "symbol": crypto_symbol,
                        "history": formatted_history,
                        "total_records": len(history),
                        "hours": hours
                    })
                }
                
            elif function_name == "list_available_cryptocurrencies":
                available_coins = db_manager.get_available_coins()
                
                return {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": json.dumps({
                        "available_cryptocurrencies": available_coins[:20],  # 상위 20개만
                        "total_count": len(available_coins)
                    })
                }
                
            else:
                return {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": json.dumps({
                        "error": f"Unknown function: {function_name}"
                    })
                }
                
        except Exception as e:
            logger.error(f"Tool 호출 처리 실패 ({function_name}): {e}")
            return {
                "tool_call_id": tool_call.id,
                "role": "tool",
                "content": json.dumps({
                    "error": f"Tool execution failed: {str(e)}"
                })
            }
    
    def process_query_with_tools(self, query: str, db_manager: DatabaseManager, code_mapper: CoinCodeMapper) -> str:
        """Tool 기반 질의 처리"""
        
        system_message = """당신은 암호화폐 전문 분석가입니다. 
사용자의 질문에 대해 실시간 데이터를 기반으로 정확하고 유용한 분석을 제공하세요.

분석 시 다음을 포함하세요:
- 현재 가격과 변동률
- 시장 동향 및 트렌드 
- 거래량 분석
- 간단한 투자 의견 (위험 경고 포함)

답변은 한국어로 3-5줄 내외로 간결하고 이해하기 쉽게 작성하세요."""

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": query}
        ]
        
        try:
            # 첫 번째 API 호출 (Tools 포함)
            response = openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
                max_tokens=800,
                temperature=0.3
            )
            
            response_message = response.choices[0].message
            
            # Tool 호출이 있는 경우
            if response_message.tool_calls:
                logger.info(f"Tool 호출 감지: {len(response_message.tool_calls)}개")
                
                # 메시지에 AI 응답 추가
                messages.append({
                    "role": "assistant",
                    "content": response_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in response_message.tool_calls
                    ]
                })
                
                # 각 Tool 호출 처리
                for tool_call in response_message.tool_calls:
                    tool_result = self.handle_tool_call(tool_call, db_manager, code_mapper)
                    messages.append(tool_result)
                
                # 최종 응답 생성
                final_response = openai_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=400,
                    temperature=0.3
                )
                
                return final_response.choices[0].message.content.strip()
            
            else:
                # Tool 호출 없이 직접 응답
                return response_message.content.strip()
                
        except Exception as e:
            logger.error(f"Tool 기반 질의 처리 실패: {e}")
            return f"⚠️ 질의 처리 중 오류가 발생했습니다: {str(e)}"
        
    def analyze_coin_data(self, coin_code: str, coin_data: Dict, history: List[Dict]) -> str:
        """코인 데이터를 분석하여 자연어 답변 생성"""
        
        # 토큰 효율적 프롬프트 생성
        prompt = self._create_analysis_prompt(coin_code, coin_data, history)
        
        try:
            response = openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "당신은 암호화폐 전문 분석가입니다. 간결하고 정확한 분석을 제공하세요."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,  # 토큰 제한
                temperature=0.3  # 일관성 있는 답변
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"LLM 분석 실패: {e}")
            return f"{coin_code} 분석 중 오류가 발생했습니다."
    
    def _create_analysis_prompt(self, coin_code: str, coin_data: Dict, history: List[Dict]) -> str:
        """토큰 효율적 분석 프롬프트 생성"""
        
        # 기본 데이터 요약
        current_price = coin_data.get('current_price', 0)
        change_rate = coin_data.get('change_rate', 0)
        trend = coin_data.get('trend', 'unknown')
        volume_spike = coin_data.get('volume_spike', False)
        volatility = coin_data.get('volatility', 'unknown')
        
        # 가격 히스토리 요약 (최근 5개 데이터 포인트만)
        recent_history = history[:5] if history else []
        history_text = ""
        if recent_history:
            prices = [float(h['trade_price']) for h in recent_history]
            history_text = f"최근 가격: {prices[0]:,.0f}원 (현재) → {prices[-1]:,.0f}원"
        
        # 간결한 프롬프트 생성 (토큰 최적화)
        prompt = f"""
코인: {coin_code}
현재가: {current_price:,.0f}원
변화율: {change_rate:.2f}%
추세: {trend}
거래량 급증: {'예' if volume_spike else '아니오'}
변동성: {volatility}
{history_text}

위 데이터를 바탕으로 3-4줄 이내로 간결한 분석을 제공하세요:
1. 현재 상태 한 줄 요약
2. 주요 포인트 (가격, 거래량, 추세)
3. 간단한 의견 (주의사항 포함)
"""
        
        return prompt
    
    def generate_response_to_query(self, query: str, coin_code: str, analysis: str) -> str:
        """사용자 질의에 맞는 답변 생성"""
        
        # 질의 유형 분석
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['어때', '분석', '전망']):
            return f"📊 **{coin_code} 분석**\n\n{analysis}"
        elif any(word in query_lower for word in ['매수', '사도', '살만']):
            return f"💰 **{coin_code} 투자 의견**\n\n{analysis}\n\n⚠️ 투자 결정은 본인 책임하에 신중히 하세요."
        elif any(word in query_lower for word in ['가격', '시세']):
            return f"💵 **{coin_code} 가격 정보**\n\n{analysis}"
        else:
            return f"🔍 **{coin_code} 정보**\n\n{analysis}"

class CoinQASystem:
    """코인 질의응답 시스템"""
    
    def __init__(self):
        self.code_mapper = CoinCodeMapper()
        self.db_manager = DatabaseManager()
        self.llm_analyzer = LLMAnalyzer()
        
        # 질의 패턴 통계
        self.query_stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'popular_coins': {},
            'query_types': {}
        }
    
    async def process_query(self, query: str) -> str:
        """사용자 질의 처리 (Tool 기반)"""
        
        self.query_stats['total_queries'] += 1
        
        try:
            # Tool 기반 질의 처리 (키워드 매칭 제거)
            response = self.llm_analyzer.process_query_with_tools(
                query, 
                self.db_manager, 
                self.code_mapper
            )
            
            # 성공 통계 업데이트 (코인 코드 추출 시도)
            coin_code = self.code_mapper.extract_coin_code(query)
            self._update_stats(coin_code or "UNKNOWN", query, True)
            
            return response
            
        except Exception as e:
            logger.error(f"질의 처리 실패: {e}")
            self.query_stats['failed_queries'] += 1
            return f"⚠️ 질의 처리 중 오류가 발생했습니다: {str(e)}"
    
    def _update_stats(self, coin_code: str, query: str, success: bool):
        """질의 통계 업데이트"""
        if success:
            self.query_stats['successful_queries'] += 1
            
            # 인기 코인 통계
            if coin_code in self.query_stats['popular_coins']:
                self.query_stats['popular_coins'][coin_code] += 1
            else:
                self.query_stats['popular_coins'][coin_code] = 1
            
            # 질의 유형 통계
            query_lower = query.lower()
            if '어때' in query_lower or '분석' in query_lower:
                query_type = 'analysis'
            elif '매수' in query_lower or '사도' in query_lower:
                query_type = 'investment'
            elif '가격' in query_lower or '시세' in query_lower:
                query_type = 'price'
            else:
                query_type = 'general'
                
            if query_type in self.query_stats['query_types']:
                self.query_stats['query_types'][query_type] += 1
            else:
                self.query_stats['query_types'][query_type] = 1
    
    def get_stats(self) -> Dict:
        """통계 정보 반환"""
        return {
            'total_queries': self.query_stats['total_queries'],
            'success_rate': self.query_stats['successful_queries'] / max(self.query_stats['total_queries'], 1) * 100,
            'top_coins': sorted(self.query_stats['popular_coins'].items(), key=lambda x: x[1], reverse=True)[:5],
            'query_types': self.query_stats['query_types']
        }

# FastAPI 웹 서버
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 전역 Q&A 시스템 인스턴스
qa_system = None

class QuestionRequest(BaseModel):
    question: str

class QuestionResponse(BaseModel):
    answer: str
    coin_code: str = ""
    timestamp: str = ""

# FastAPI 앱 생성
app = FastAPI(
    title="Coin Q&A System",
    description="코인 질의응답 시스템",
    version="1.0.0"
)

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인 허용
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

@app.on_event("startup")
async def startup_event():
    """서비스 시작 시 Q&A 시스템 초기화"""
    global qa_system
    qa_system = CoinQASystem()
    logger.info("코인 Q&A 시스템 초기화 완료")

@app.post("/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """코인 질의응답 처리"""
    try:
        if not qa_system:
            raise HTTPException(status_code=500, detail="QA 시스템이 초기화되지 않았습니다.")
        
        # 질의 처리
        answer = await qa_system.process_query(request.question)
        
        # 코인 코드 추출 (응답에 포함하기 위해)
        coin_code = qa_system.code_mapper.extract_coin_code(request.question) or ""
        
        return QuestionResponse(
            answer=answer,
            coin_code=coin_code,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"질의 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=f"질의 처리 중 오류가 발생했습니다: {str(e)}")

@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "service": "coin-qa-system",
        "stats": qa_system.get_stats() if qa_system else {}
    }

@app.get("/stats")
async def get_stats():
    """통계 정보 조회"""
    if not qa_system:
        raise HTTPException(status_code=500, detail="QA 시스템이 초기화되지 않았습니다.")
    
    return qa_system.get_stats()

# 웹 서버 테스트 함수
async def test_qa_system():
    """QA 시스템 테스트 (Docker용)"""
    qa_system = CoinQASystem()
    
    print("🚀 코인 질의응답 시스템 시작!")
    print("Docker 컨테이너에서 자동 테스트를 실행합니다.")
    print("-" * 50)
    
    # 테스트 질의 목록 (Tool 기반 - 다양한 자연어 패턴)
    test_queries = [
        "비트코인 현재 상황 어떤가요?",
        "Ethereum이 오늘 많이 올랐나요?", 
        "요즘 알트코인 중에 뭐가 좋을까요?",
        "XRP 투자해도 될까요?",
        "암호화폐 시장 전체적으로 어떤 상황인가요?",
        "What's the current Bitcoin price trend?",
        "최근에 급등한 코인 있나요?"
    ]
    
    for query in test_queries:
        try:
            print(f"\n💬 테스트 질문: {query}")
            print("🔍 분석 중...")
            response = await qa_system.process_query(query)
            print(f"\n{response}")
            print("-" * 50)
            
            # 2초 대기
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
    
    # 통계 출력
    stats = qa_system.get_stats()
    print(f"\n📊 최종 통계:")
    print(f"- 총 질의 수: {stats['total_queries']}")
    print(f"- 성공률: {stats['success_rate']:.1f}%")
    print(f"- 인기 코인: {stats['top_coins']}")
    print(f"- 질의 유형: {stats['query_types']}")
    
    print("\n✅ 테스트 완료! 시스템이 대기 상태로 전환됩니다.")
    
    # 무한 대기 (컨테이너 유지)
    while True:
        await asyncio.sleep(60)
        print("🔄 시스템 정상 동작 중...")

if __name__ == "__main__":
    import sys
    import os
    
    # Docker 환경에서는 웹 서버 모드로 실행
    if os.getenv("DOCKER_ENV") == "true":
        # 웹 서버 모드
        uvicorn.run(app, host="0.0.0.0", port=8080)
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        # 테스트 모드
        asyncio.run(test_qa_system())
    else:
        # 웹 서버 모드
        uvicorn.run(app, host="0.0.0.0", port=8080)