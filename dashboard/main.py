#!/usr/bin/env python3
"""
FastAPI 기반 Upbit LLM Analytics Dashboard 서버
- WebSocket 프록시 (mvp-market-summary)
- REST API 프록시 (mvp-coin-qa, mcp-server)
- 정적 파일 서빙
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import httpx
import asyncio
import json
import logging
from pathlib import Path
import websockets
from typing import Dict, Any
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="Upbit LLM Analytics Dashboard",
    description="실시간 암호화폐 분석 대시보드",
    version="1.0.0"
)

# 환경변수 설정
MARKET_SUMMARY_HOST = os.getenv("MARKET_SUMMARY_HOST", "mvp-market-summary")
COIN_QA_HOST = os.getenv("COIN_QA_HOST", "mvp-coin-qa")
MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "mcp-server")

MARKET_SUMMARY_PORT = os.getenv("MARKET_SUMMARY_PORT", "8765")
COIN_QA_PORT = os.getenv("COIN_QA_PORT", "8080")
MCP_SERVER_PORT = os.getenv("MCP_SERVER_PORT", "9093")

# TimescaleDB 연결 설정
DB_CONFIG = {
    "host": os.getenv("TIMESCALEDB_HOST", "timescaledb"),
    "port": os.getenv("TIMESCALEDB_PORT", "5432"),
    "database": os.getenv("TIMESCALEDB_DATABASE", "upbit_analytics"),
    "user": os.getenv("TIMESCALEDB_USER", "upbit_user"),
    "password": os.getenv("TIMESCALEDB_PASSWORD", "upbit_password")
}

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    """메인 대시보드 페이지 반환"""
    dashboard_dir = Path(__file__).parent
    index_path = dashboard_dir / "index.html"
    
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(), status_code=200)
    else:
        return HTMLResponse(content="<h1>Dashboard not found</h1>", status_code=404)

@app.websocket("/ws/market-summary")
async def websocket_market_summary_proxy(websocket: WebSocket):
    """
    WebSocket 프록시 - mvp-market-summary 서비스와 연결
    실시간 시장 요약 데이터를 브라우저에 중계
    """
    await websocket.accept()
    logger.info("WebSocket 클라이언트 연결됨")
    
    backend_uri = f"ws://{MARKET_SUMMARY_HOST}:{MARKET_SUMMARY_PORT}"
    
    try:
        # 백엔드 WebSocket 서버에 연결
        async with websockets.connect(backend_uri) as backend_ws:
            logger.info(f"백엔드 WebSocket 연결 성공: {backend_uri}")
            
            # 메시지 중계 태스크
            async def relay_to_client():
                try:
                    async for message in backend_ws:
                        await websocket.send_text(message)
                except websockets.exceptions.ConnectionClosed:
                    logger.info("백엔드 WebSocket 연결 종료")
                except Exception as e:
                    logger.error(f"백엔드 → 클라이언트 중계 오류: {e}")
            
            async def relay_to_backend():
                try:
                    while True:
                        message = await websocket.receive_text()
                        await backend_ws.send(message)
                except WebSocketDisconnect:
                    logger.info("클라이언트 WebSocket 연결 종료")
                except Exception as e:
                    logger.error(f"클라이언트 → 백엔드 중계 오류: {e}")
            
            # 양방향 중계 시작
            await asyncio.gather(
                relay_to_client(),
                relay_to_backend()
            )
            
    except Exception as e:
        logger.error(f"WebSocket 프록시 오류: {e}")
        await websocket.close(code=1011, reason=f"Backend connection failed: {e}")

@app.post("/api/ask")
async def ask_question_proxy(question_data: Dict[str, Any]):
    """
    REST API 프록시 - mvp-coin-qa 서비스
    코인 Q&A 질문을 백엔드로 전달하고 응답 반환
    """
    backend_url = f"http://{COIN_QA_HOST}:{COIN_QA_PORT}/ask"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                backend_url,
                json=question_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Q&A 서비스 오류: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Q&A service error: {response.text}"
                )
                
    except httpx.TimeoutException:
        logger.error("Q&A 서비스 타임아웃")
        raise HTTPException(status_code=504, detail="Q&A service timeout")
    except Exception as e:
        logger.error(f"Q&A 프록시 오류: {e}")
        raise HTTPException(status_code=500, detail=f"Q&A proxy error: {e}")

@app.post("/api/mcp")
async def mcp_query_proxy(payload: Dict[str, Any]):
    """
    MCP JSONRPC 프록시 - mcp-server 서비스 (fallback to mock data)
    MCP 쿼리를 백엔드로 전달하고 응답 반환 (연결 실패 시 mock 데이터)
    """
    backend_url = f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/jsonrpc"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                backend_url,
                json=payload,
                timeout=5.0  # 짧은 타임아웃으로 빠른 fallback
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"MCP 서비스 오류: {response.status_code}, fallback to mock data")
                return get_mock_mcp_response(payload)
                
    except (httpx.TimeoutException, httpx.ConnectError, Exception) as e:
        logger.warning(f"MCP 서비스 연결 실패, mock 데이터 사용: {e}")
        return get_mock_mcp_response(payload)

def get_mock_mcp_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    """MCP 서버 연결 실패 시 mock 데이터 반환"""
    function_name = payload.get("params", {}).get("name", "")
    
    if function_name == "get_market_overview":
        mock_data = {
            "rising_coins": 127,
            "falling_coins": 50,
            "top_gainer": "KRW-BTC (+2.1%)",
            "highest_volume": "KRW-ETH"
        }
    elif function_name == "detect_anomalies":
        mock_data = []  # 이상 거래 없음
    elif function_name == "calculate_rsi":
        mock_data = {
            "rsi_value": 52.3,
            "signal": "중립 구간"
        }
    elif function_name == "calculate_bollinger_bands":
        mock_data = {
            "upper_band": "43,500,000",
            "middle_band": "41,200,000", 
            "lower_band": "38,900,000",
            "signal": "중간선 근처 - 중립"
        }
    else:
        mock_data = {"error": f"알 수 없는 함수: {function_name}"}
    
    return {
        "jsonrpc": "2.0",
        "result": {
            "content": [{"text": json.dumps(mock_data, ensure_ascii=False)}]
        },
        "id": payload.get("id", 1)
    }

@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "service": "dashboard-server",
        "backend_services": {
            "market_summary": f"{MARKET_SUMMARY_HOST}:{MARKET_SUMMARY_PORT}",
            "coin_qa": f"{COIN_QA_HOST}:{COIN_QA_PORT}",
            "mcp_server": f"{MCP_SERVER_HOST}:{MCP_SERVER_PORT}"
        }
    }

@app.get("/api/status")
async def backend_status():
    """백엔드 서비스 상태 확인"""
    status = {}
    
    # Q&A 서비스 상태 확인
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{COIN_QA_HOST}:{COIN_QA_PORT}/health", timeout=5.0)
            status["coin_qa"] = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception as e:
        status["coin_qa"] = f"error: {e}"
    
    # MCP 서버 상태 확인
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/health", timeout=5.0)
            status["mcp_server"] = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception as e:
        status["mcp_server"] = f"error: {e}"
    
    return status

def get_db_connection():
    """TimescaleDB 연결 객체 반환"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"DB 연결 오류: {e}")
        return None

@app.get("/api/prediction/{coin_code}")
async def get_coin_prediction(coin_code: str):
    """
    코인 예측 API - 통합 예측 모델 결과 반환
    Example: /api/prediction/KRW-BTC
    """
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # 통합 예측 모델 실행
            cursor.execute(
                "SELECT * FROM get_comprehensive_prediction(%s, 5);",
                (coin_code,)
            )
            prediction_result = cursor.fetchone()
            
            if not prediction_result:
                raise HTTPException(status_code=404, detail=f"No prediction data for {coin_code}")
            
            # 추가 기술적 지표 데이터
            cursor.execute(
                "SELECT * FROM get_technical_analysis(%s, 1);",
                (coin_code,)
            )
            technical_result = cursor.fetchone()
            
            # 이동평균 신호
            cursor.execute(
                "SELECT * FROM calculate_moving_average_signals(%s, 5, 15, 60) ORDER BY time DESC LIMIT 1;",
                (coin_code,)
            )
            ma_result = cursor.fetchone()
            
            # RSI 다이버전스
            cursor.execute(
                "SELECT * FROM detect_rsi_divergence(%s, 20) ORDER BY time DESC LIMIT 1;",
                (coin_code,)
            )
            rsi_div_result = cursor.fetchone()
            
            # 볼린저밴드 브레이크아웃
            cursor.execute(
                "SELECT * FROM predict_bollinger_breakout(%s, 0.02) ORDER BY time DESC LIMIT 1;",
                (coin_code,)
            )
            bb_result = cursor.fetchone()
            
            conn.close()
            
            # 응답 데이터 구성
            response_data = {
                "coin_code": coin_code,
                "prediction": dict(prediction_result) if prediction_result else {},
                "technical_analysis": dict(technical_result) if technical_result else {},
                "moving_average_signals": dict(ma_result) if ma_result else {},
                "rsi_divergence": dict(rsi_div_result) if rsi_div_result else {},
                "bollinger_breakout": dict(bb_result) if bb_result else {},
                "timestamp": asyncio.get_event_loop().time()
            }
            
            return response_data
            
    except Exception as e:
        logger.error(f"예측 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction API error: {e}")

@app.get("/api/predictions/top-coins")
async def get_top_coins_predictions():
    """
    주요 코인들의 예측 결과 요약
    BTC, ETH, XRP 등 주요 코인들의 예측 신호 반환
    """
    top_coins = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-ADA", "KRW-DOT"]
    predictions = {}
    
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            for coin in top_coins:
                try:
                    cursor.execute(
                        "SELECT * FROM get_comprehensive_prediction(%s, 5);",
                        (coin,)
                    )
                    result = cursor.fetchone()
                    
                    if result:
                        predictions[coin] = {
                            "current_price": float(result["current_price"]),
                            "predicted_price_5m": float(result["predicted_price_5m"]),
                            "overall_signal": result["overall_signal"],
                            "confidence_score": result["confidence_score"],
                            "risk_level": result["risk_level"],
                            "recommendation": result["recommendation"]
                        }
                except Exception as e:
                    logger.warning(f"{coin} 예측 오류: {e}")
                    predictions[coin] = {"error": str(e)}
        
        conn.close()
        
        return {
            "predictions": predictions,
            "timestamp": asyncio.get_event_loop().time(),
            "total_coins": len(predictions)
        }
        
    except Exception as e:
        logger.error(f"주요 코인 예측 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"Top coins prediction API error: {e}")

@app.get("/api/analysis/volume-signals")
async def get_volume_signals():
    """
    거래량 신호 분석 - 비정상 거래량 활동 탐지
    """
    major_coins = ["KRW-BTC", "KRW-ETH", "KRW-XRP"]
    
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        volume_signals = {}
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            for coin in major_coins:
                try:
                    cursor.execute(
                        "SELECT * FROM analyze_volume_confirmation(%s, 1.5) ORDER BY time DESC LIMIT 5;",
                        (coin,)
                    )
                    results = cursor.fetchall()
                    
                    volume_signals[coin] = [dict(row) for row in results] if results else []
                    
                except Exception as e:
                    logger.warning(f"{coin} 거래량 분석 오류: {e}")
                    volume_signals[coin] = []
        
        conn.close()
        
        return {
            "volume_signals": volume_signals,
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except Exception as e:
        logger.error(f"거래량 신호 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"Volume signals API error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)