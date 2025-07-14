#!/bin/bash

# Upbit LLM Analytics - Quick Start Script
# 새 세션에서 바로 시작할 수 있도록 모든 서비스를 자동으로 시작

echo "🚀 Starting Upbit LLM Analytics Platform..."
echo "================================================="

# 1. 모든 컨테이너 정리
echo "1. Cleaning up existing containers..."
docker compose -f mcp-compose.yml down 2>/dev/null || true
docker compose -f timescaledb-compose.yml down 2>/dev/null || true  
docker compose -f kafka-compose.yml down 2>/dev/null || true

# 2. 통합 서비스 시작 (TimescaleDB + MCP Server + Kafka)
echo "2. Starting integrated services..."
docker compose -f mcp-compose.yml up -d

# 3. 서비스 상태 확인
echo "3. Waiting for services to be ready..."
sleep 20

# 4. 서비스 상태 확인
echo "4. Checking service status..."
echo "   - TimescaleDB:"
docker ps --filter "name=timescaledb" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo "   - MCP Server:"
docker ps --filter "name=upbit-mcp-server" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo "   - Kafka:"
docker ps --filter "name=kafka" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 5. 연결 테스트
echo "5. Testing connections..."
echo "   - TimescaleDB health:"
docker exec timescaledb psql -h localhost -U upbit_user -d upbit_analytics -c "SELECT COUNT(*) FROM ticker_data;" 2>/dev/null || echo "   ❌ TimescaleDB not ready"

echo "   - MCP Server health:"
curl -s http://localhost:9093/status | grep -q "ok" && echo "   ✅ MCP Server ready" || echo "   ❌ MCP Server not ready"

echo ""
echo "🎉 Services Started Successfully!"
echo "================================================="
echo "Available services:"
echo "  - TimescaleDB: localhost:5432"
echo "  - MCP Server: localhost:9093"
echo "  - Kafka: localhost:9092"
echo ""
echo "Quick tests:"
echo "  - Test MCP: python test_mcp_connection.py"
echo "  - Test Consumer: python upbit-kafka/consumer.py"
echo "  - Test Producer: python upbit-kafka/producer.py"
echo ""
echo "Next steps:"
echo "  1. Implement core MCP functions (get_coin_summary, get_market_movers, detect_anomalies)"
echo "  2. Test LLM integration"
echo "  3. Build MVP features"