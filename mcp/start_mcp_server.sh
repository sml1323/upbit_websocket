#!/bin/bash

# FreePeak db-mcp-server 시작 스크립트
# Upbit LLM Analytics Platform용

echo "🚀 Starting FreePeak DB MCP Server for Upbit Analytics..."

# 현재 디렉토리 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.json"

# config.json 파일 존재 확인
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ config.json not found at $CONFIG_FILE"
    echo "Please create config.json file first"
    exit 1
fi

echo "📋 Using config file: $CONFIG_FILE"

# Docker 이미지 pull
echo "📥 Pulling latest FreePeak db-mcp-server image..."
docker pull freepeak/db-mcp-server:latest

# 기존 컨테이너가 실행 중이면 중지
echo "🔄 Stopping existing containers..."
docker stop upbit-mcp-server 2>/dev/null || true
docker rm upbit-mcp-server 2>/dev/null || true

# MCP 서버 실행
echo "🏃 Starting MCP Server..."
docker run -d \
  --name upbit-mcp-server \
  --network host \
  -v "$CONFIG_FILE":/app/config.json \
  -e TRANSPORT_MODE=sse \
  -e CONFIG_PATH=/app/config.json \
  freepeak/db-mcp-server:latest

# 상태 확인
sleep 3
if docker ps | grep -q upbit-mcp-server; then
    echo "✅ MCP Server started successfully!"
    echo "🌐 Server running at: http://localhost:9092"
    echo "📊 Database: TimescaleDB (coin database)"
    echo ""
    echo "📋 Available endpoints:"
    echo "  - Health check: curl http://localhost:9092/health"
    echo "  - MCP tools: http://localhost:9092/v1/tools"
    echo ""
    echo "📖 Logs: docker logs upbit-mcp-server"
    echo "🛑 Stop: docker stop upbit-mcp-server"
else
    echo "❌ Failed to start MCP Server"
    echo "📖 Check logs: docker logs upbit-mcp-server"
    exit 1
fi