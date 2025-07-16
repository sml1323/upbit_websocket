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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)