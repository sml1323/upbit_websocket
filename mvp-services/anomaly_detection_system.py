#!/usr/bin/env python3
"""
이상 탐지 시스템
- 거래량, 가격 급변 등의 이상 패턴 탐지
- 실시간 알림 및 분석 제공
- 통계적 임계값 기반 탐지
"""

import asyncio
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import numpy as np
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
    
    def get_recent_data(self, hours: int = 1) -> List[Dict]:
        """최근 데이터 조회"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            code, 
                            trade_price, 
                            trade_volume,
                            change_rate,
                            acc_trade_volume,
                            time
                        FROM ticker_data
                        WHERE time >= NOW() - INTERVAL '%s hours'
                        ORDER BY time DESC
                        LIMIT 1000
                    """, (hours,))
                    
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"데이터 조회 실패: {e}")
            return []
    
    def get_db_anomalies(self, timeframe_hours: int = 1, sensitivity: int = 3) -> List[Dict]:
        """DB 함수를 통한 이상 탐지"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM detect_anomalies(%s, %s)", (timeframe_hours, sensitivity))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"DB 이상 탐지 실패: {e}")
            return []

class AnomalyDetector:
    """이상 패턴 탐지기"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        
    def detect_volume_spikes(self, data: List[Dict], threshold: float = 3.0) -> List[Dict]:
        """거래량 급증 탐지"""
        anomalies = []
        
        # 코인별로 그룹화
        coin_data = {}
        for row in data:
            code = row['code']
            if code not in coin_data:
                coin_data[code] = []
            coin_data[code].append(row)
        
        for code, records in coin_data.items():
            if len(records) < 5:  # 최소 5개 데이터 필요
                continue
                
            volumes = [float(r['trade_volume']) for r in records]
            mean_volume = np.mean(volumes)
            std_volume = np.std(volumes)
            
            if std_volume == 0:
                continue
            
            # 최신 거래량이 평균보다 threshold 표준편차 이상 높은 경우
            latest_volume = volumes[0]
            z_score = (latest_volume - mean_volume) / std_volume
            
            if z_score > threshold:
                anomalies.append({
                    'type': 'volume_spike',
                    'code': code,
                    'current_volume': latest_volume,
                    'avg_volume': mean_volume,
                    'z_score': z_score,
                    'severity': 'high' if z_score > 5 else 'medium',
                    'timestamp': records[0]['time']
                })
        
        return anomalies
    
    def detect_price_anomalies(self, data: List[Dict], threshold: float = 5.0) -> List[Dict]:
        """가격 급변 탐지"""
        anomalies = []
        
        for row in data:
            change_rate = abs(float(row.get('change_rate', 0)))
            
            if change_rate > threshold:
                anomalies.append({
                    'type': 'price_spike',
                    'code': row['code'],
                    'change_rate': row['change_rate'],
                    'current_price': row['trade_price'],
                    'severity': 'high' if change_rate > 10 else 'medium',
                    'timestamp': row['time']
                })
        
        return anomalies

class AnomalyNotifier:
    """이상 알림 시스템"""
    
    def __init__(self):
        self.notifications = []
    
    def send_notification(self, anomaly: Dict):
        """알림 전송 (로그 출력)"""
        severity_emoji = {
            'high': '🚨',
            'medium': '⚠️',
            'low': '📢'
        }
        
        emoji = severity_emoji.get(anomaly.get('severity', 'low'), '📢')
        
        message = f"{emoji} {anomaly['type'].upper()} 탐지!\n"
        message += f"코인: {anomaly['code']}\n"
        
        if anomaly['type'] == 'volume_spike':
            message += f"현재 거래량: {anomaly['current_volume']:,.0f}\n"
            message += f"평균 거래량: {anomaly['avg_volume']:,.0f}\n"
            message += f"Z-Score: {anomaly['z_score']:.2f}"
        elif anomaly['type'] == 'price_spike':
            message += f"변화율: {anomaly['change_rate']:.2f}%\n"
            message += f"현재 가격: {anomaly['current_price']:,.0f}원"
        
        logger.info(message)
        self.notifications.append({
            'message': message,
            'timestamp': datetime.now(timezone.utc),
            'anomaly': anomaly
        })

class AnomalyDetectionSystem:
    """통합 이상 탐지 시스템"""
    
    def __init__(self):
        self.detector = AnomalyDetector()
        self.notifier = AnomalyNotifier()
        self.running = False
        
    async def start_monitoring(self):
        """모니터링 시작"""
        self.running = True
        logger.info("🔍 이상 탐지 시스템 시작")
        
        while self.running:
            try:
                # 최근 1시간 데이터 분석
                recent_data = self.detector.db_manager.get_recent_data(1)
                
                if not recent_data:
                    logger.warning("분석할 데이터가 없습니다")
                    await asyncio.sleep(60)
                    continue
                
                # 이상 패턴 탐지
                volume_anomalies = self.detector.detect_volume_spikes(recent_data)
                price_anomalies = self.detector.detect_price_anomalies(recent_data)
                
                # DB 함수 기반 탐지도 추가
                db_anomalies = self.detector.db_manager.get_db_anomalies(1, 3)
                
                # 알림 전송
                all_anomalies = volume_anomalies + price_anomalies
                
                if all_anomalies:
                    logger.info(f"🚨 {len(all_anomalies)}개 이상 패턴 탐지!")
                    for anomaly in all_anomalies:
                        self.notifier.send_notification(anomaly)
                else:
                    logger.info("✅ 정상 상태 - 이상 패턴 없음")
                
                # DB 함수 결과도 출력
                if db_anomalies:
                    logger.info(f"📊 DB 함수 탐지: {len(db_anomalies)}개 이상 패턴")
                    for db_anomaly in db_anomalies[:3]:  # 최대 3개까지만 출력
                        logger.info(f"  - {db_anomaly.get('code', 'N/A')}: {db_anomaly.get('anomaly_type', 'N/A')} ({db_anomaly.get('severity', 'N/A')})")
                
                # 5분마다 실행
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"모니터링 오류: {e}")
                await asyncio.sleep(60)
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.running = False
        logger.info("이상 탐지 시스템 중지")

async def main():
    """메인 함수"""
    system = AnomalyDetectionSystem()
    
    try:
        await system.start_monitoring()
    except KeyboardInterrupt:
        system.stop_monitoring()
        logger.info("사용자에 의해 종료됨")

if __name__ == "__main__":
    asyncio.run(main())