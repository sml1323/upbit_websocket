#!/usr/bin/env python3
"""
대시보드 서버 - 간단한 HTTP 서버로 정적 파일 제공
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

class CORSHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """CORS 헤더를 추가한 HTTP 요청 핸들러"""
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        """OPTIONS 요청 처리 (CORS preflight)"""
        self.send_response(200)
        self.end_headers()

def start_dashboard_server(port=8000):
    """대시보드 서버 시작"""
    
    # 현재 스크립트가 있는 디렉토리로 이동
    dashboard_dir = Path(__file__).parent
    os.chdir(dashboard_dir)
    
    print(f"🌐 대시보드 서버 시작 중...")
    print(f"📂 서빙 디렉토리: {dashboard_dir}")
    print(f"🔗 URL: http://localhost:{port}")
    print(f"🔗 WSL에서 접속: http://172.31.65.200:{port}")
    print(f"⚠️  중지하려면 Ctrl+C를 누르세요")
    
    try:
        with socketserver.TCPServer(("", port), CORSHTTPRequestHandler) as httpd:
            print(f"✅ 서버가 포트 {port}에서 실행 중입니다")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n🛑 서버 중지됨")
    except Exception as e:
        print(f"❌ 서버 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Upbit 대시보드 서버')
    parser.add_argument('--port', type=int, default=8000, help='서버 포트 (기본값: 8000)')
    
    args = parser.parse_args()
    start_dashboard_server(args.port)