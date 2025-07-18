#!/usr/bin/env python3
"""
실시간 시장 요약 생성기 (5분 간격)
- 전체 시장 분위기 및 주요 움직임 요약
- 토큰 효율성 99% 달성 (50K→500토큰 목표)
- WebSocket 또는 polling 방식으로 실시간 알림
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import websockets
import threading
from dataclasses import dataclass, asdict
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

@dataclass
class MarketSummary:
    """시장 요약 데이터 클래스"""
    timestamp: str
    total_coins: int
    rising_coins: int
    falling_coins: int
    neutral_coins: int
    market_sentiment: str
    top_gainer: str
    top_loser: str
    highest_volume: str
    summary_text: str
    alert_level: str

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
    
    def get_market_overview(self) -> Optional[Dict]:
        """시장 개요 데이터 조회"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM get_market_overview()")
                    result = cur.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            logger.error(f"시장 개요 조회 실패: {e}")
            return None
    
    def get_top_movers(self, limit: int = 5) -> List[Dict]:
        """상위 상승/하락 코인 조회"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # 상위 상승 코인
                    cur.execute(
                        "SELECT * FROM get_market_movers('gainers', %s, 1)",
                        (limit,)
                    )
                    gainers = [dict(row) for row in cur.fetchall()]
                    
                    # 상위 하락 코인
                    cur.execute(
                        "SELECT * FROM get_market_movers('losers', %s, 1)",
                        (limit,)
                    )
                    losers = [dict(row) for row in cur.fetchall()]
                    
                    return {'gainers': gainers, 'losers': losers}
        except Exception as e:
            logger.error(f"상위 무버 조회 실패: {e}")
            return {'gainers': [], 'losers': []}
    
    def get_anomalies(self, sensitivity: int = 3) -> List[Dict]:
        """이상 거래 탐지"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM detect_anomalies(1, %s)",
                        (sensitivity,)
                    )
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"이상 거래 탐지 실패: {e}")
            return []

class MarketSummaryGenerator:
    """시장 요약 생성기"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        
    def generate_summary(self) -> Optional[MarketSummary]:
        """시장 요약 생성 (토큰 최적화)"""
        try:
            # 1. 기본 시장 개요
            overview = self.db.get_market_overview()
            if not overview:
                logger.warning("시장 개요 데이터 없음")
                return None
            
            # 2. 상위 무버들
            movers = self.db.get_top_movers(3)
            
            # 3. 이상 거래 탐지
            anomalies = self.db.get_anomalies(3)
            
            # 4. 토큰 효율적 요약 텍스트 생성
            summary_text = self._create_summary_text(overview, movers, anomalies)
            
            # 5. 알림 레벨 결정
            alert_level = self._determine_alert_level(overview, anomalies)
            
            return MarketSummary(
                timestamp=datetime.now(timezone.utc).isoformat(),
                total_coins=overview.get('total_coins', 0),
                rising_coins=overview.get('rising_coins', 0),
                falling_coins=overview.get('falling_coins', 0),
                neutral_coins=overview.get('neutral_coins', 0),
                market_sentiment=overview.get('market_sentiment', 'unknown'),
                top_gainer=overview.get('top_gainer', ''),
                top_loser=overview.get('top_loser', ''),
                highest_volume=overview.get('highest_volume', ''),
                summary_text=summary_text,
                alert_level=alert_level
            )
            
        except Exception as e:
            logger.error(f"시장 요약 생성 실패: {e}")
            return None
    
    def _create_summary_text(self, overview: Dict, movers: Dict, anomalies: List[Dict]) -> str:
        """토큰 효율적 요약 텍스트 생성 (50K→500토큰 목표)"""
        try:
            # 시장 분위기
            sentiment = overview.get('market_sentiment', 'mixed')
            rising = overview.get('rising_coins', 0)
            falling = overview.get('falling_coins', 0)
            total = overview.get('total_coins', 1)
            
            # 간결한 시장 상태
            market_state = f"📊 {sentiment.upper()} | ↗️{rising} ↘️{falling} ({total}코인)"
            
            # 주요 움직임 (상위 3개만)
            top_moves = []
            if movers.get('gainers'):
                top_gain = movers['gainers'][0]
                top_moves.append(f"🔥 {top_gain['code']} +{top_gain['change_rate']:.1f}%")
            
            if movers.get('losers'):
                top_loss = movers['losers'][0]
                top_moves.append(f"❄️ {top_loss['code']} {top_loss['change_rate']:.1f}%")
            
            # 이상 거래 (critical/high만)
            critical_alerts = []
            for anomaly in anomalies[:3]:  # 최대 3개만
                if anomaly['severity'] in ['critical', 'high']:
                    icon = '🚨' if anomaly['severity'] == 'critical' else '⚠️'
                    critical_alerts.append(f"{icon} {anomaly['code']}")
            
            # 최종 요약 조합 (토큰 효율적)
            parts = [market_state]
            if top_moves:
                parts.append(" | ".join(top_moves))
            if critical_alerts:
                parts.append(" | ".join(critical_alerts))
            
            return " | ".join(parts)
            
        except Exception as e:
            logger.error(f"요약 텍스트 생성 실패: {e}")
            return f"시장 요약 생성 오류: {str(e)}"
    
    def _determine_alert_level(self, overview: Dict, anomalies: List[Dict]) -> str:
        """알림 레벨 결정"""
        try:
            # Critical 이상 거래가 있으면 high
            if any(a['severity'] == 'critical' for a in anomalies):
                return 'high'
            
            # High 이상 거래가 3개 이상이면 medium
            if len([a for a in anomalies if a['severity'] == 'high']) >= 3:
                return 'medium'
            
            # 시장이 매우 bullish 또는 bearish면 medium
            sentiment = overview.get('market_sentiment', 'mixed')
            if sentiment in ['bullish', 'bearish']:
                return 'medium'
            
            return 'low'
            
        except Exception as e:
            logger.error(f"알림 레벨 결정 실패: {e}")
            return 'low'

class WebSocketNotifier:
    """WebSocket 실시간 알림 시스템"""
    
    def __init__(self, port: int = 8765):
        self.port = port
        self.clients = set()
        self.server = None
        
    async def register_client(self, websocket, path=None):
        """클라이언트 등록"""
        self.clients.add(websocket)
        logger.info(f"클라이언트 연결: {websocket.remote_address}")
        
        # 새 클라이언트에게 즉시 최신 요약 전송
        await self._send_immediate_summary(websocket)
        
        try:
            await websocket.wait_closed()
        finally:
            self.clients.remove(websocket)
            logger.info(f"클라이언트 해제: {websocket.remote_address}")
    
    async def _send_immediate_summary(self, websocket):
        """새 클라이언트에게 즉시 요약 전송"""
        try:
            # 전역 인스턴스들 사용
            if hasattr(self, '_summary_generator'):
                summary = self._summary_generator.generate_summary()
                
                if summary:
                    message = json.dumps(asdict(summary), ensure_ascii=False)
                    await websocket.send(message)
                    logger.info("새 클라이언트에게 즉시 요약 전송")
        except Exception as e:
            logger.error(f"즉시 요약 전송 실패: {e}")
    
    def set_summary_generator(self, summary_generator):
        """요약 생성기 설정 (외부에서 설정)"""
        self._summary_generator = summary_generator
    
    async def broadcast_summary(self, summary: MarketSummary):
        """모든 클라이언트에게 요약 브로드캐스트"""
        if not self.clients:
            return
        
        message = json.dumps(asdict(summary), ensure_ascii=False)
        
        # 연결이 끊긴 클라이언트 제거
        disconnected = set()
        for client in self.clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
        
        self.clients -= disconnected
        
        if self.clients:
            logger.info(f"시장 요약 브로드캐스트: {len(self.clients)}명")
    
    async def start_server(self):
        """WebSocket 서버 시작"""
        self.server = await websockets.serve(
            self.register_client,
            "0.0.0.0",
            self.port
        )
        logger.info(f"WebSocket 서버 시작: ws://0.0.0.0:{self.port}")

class RealtimeMarketSummaryService:
    """실시간 시장 요약 서비스"""
    
    def __init__(self, interval_minutes: int = 1):  # 1분으로 단축
        self.interval_minutes = interval_minutes
        self.db_manager = DatabaseManager()
        self.summary_generator = MarketSummaryGenerator(self.db_manager)
        self.websocket_notifier = WebSocketNotifier()
        self.running = False
        
    async def start(self):
        """서비스 시작"""
        logger.info("실시간 시장 요약 서비스 시작")
        self.running = True
        
        # WebSocket 알리미에 요약 생성기 설정
        self.websocket_notifier.set_summary_generator(self.summary_generator)
        
        # WebSocket 서버 시작
        await self.websocket_notifier.start_server()
        
        # 초기 요약 생성
        await self._generate_and_broadcast()
        
        # 주기적 요약 생성
        while self.running:
            await asyncio.sleep(self.interval_minutes * 60)
            await self._generate_and_broadcast()
    
    async def _generate_and_broadcast(self):
        """요약 생성 및 브로드캐스트"""
        try:
            summary = self.summary_generator.generate_summary()
            if summary:
                # 콘솔 출력
                print(f"\n[{summary.timestamp}] 시장 요약:")
                print(f"알림 레벨: {summary.alert_level.upper()}")
                print(f"요약: {summary.summary_text}")
                
                # WebSocket 브로드캐스트
                await self.websocket_notifier.broadcast_summary(summary)
                
                # 파일 저장 (옵션)
                self._save_summary_to_file(summary)
            else:
                logger.warning("시장 요약 생성 실패")
                
        except Exception as e:
            logger.error(f"요약 생성 및 브로드캐스트 실패: {e}")
    
    def _save_summary_to_file(self, summary: MarketSummary):
        """요약을 파일에 저장 (로그 용도)"""
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            log_file = log_dir / "market_summary.log"
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{summary.timestamp} | {summary.alert_level} | {summary.summary_text}\n")
                
        except Exception as e:
            logger.error(f"파일 저장 실패: {e}")
    
    def stop(self):
        """서비스 중지"""
        self.running = False
        logger.info("실시간 시장 요약 서비스 중지")

# CLI 실행 함수
async def main():
    """메인 실행 함수"""
    service = RealtimeMarketSummaryService(interval_minutes=5)
    
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("사용자 중단 요청")
    except Exception as e:
        logger.error(f"서비스 실행 오류: {e}")
    finally:
        service.stop()

if __name__ == "__main__":
    asyncio.run(main())