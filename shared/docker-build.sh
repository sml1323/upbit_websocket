#!/bin/bash

# Docker build script for Upbit Analytics Platform
# This script builds the base image and all service images

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Building Upbit Analytics Platform Docker images...${NC}"

# Build base image first
echo -e "${YELLOW}Building base Python image...${NC}"
docker build -f shared/Dockerfile.python-base -t upbit-python-base:latest .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Base image built successfully${NC}"
else
    echo -e "${RED}❌ Base image build failed${NC}"
    exit 1
fi

# Function to build service image
build_service() {
    local service_dir=$1
    local service_name=$2
    local dockerfile=$3
    
    echo -e "${YELLOW}Building $service_name image...${NC}"
    
    if [ -f "$dockerfile" ]; then
        # Use custom Dockerfile if exists
        docker build -f "$dockerfile" -t "upbit-$service_name:latest" "$service_dir"
    else
        # Use shared service Dockerfile
        docker build -f shared/Dockerfile.python-service \
            --build-arg SERVICE_DIR="$service_dir" \
            --build-arg SERVICE_NAME="$service_name" \
            -t "upbit-$service_name:latest" .
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $service_name image built successfully${NC}"
    else
        echo -e "${RED}❌ $service_name image build failed${NC}"
        return 1
    fi
}

# Build all services
echo -e "${YELLOW}Building service images...${NC}"

# Producer service
build_service "upbit-kafka" "producer" "upbit-kafka/Dockerfile.producer"

# Consumer service  
build_service "upbit-kafka" "consumer" "upbit-kafka/Dockerfile.consumer"

# MVP services
build_service "mvp-services" "mvp-services" "mvp-services/Dockerfile"

# Dashboard service
build_service "dashboard" "dashboard" "dashboard/Dockerfile.dashboard"

# Dashboard React service (if needed)
if [ -f "dashboard-react/Dockerfile" ]; then
    echo -e "${YELLOW}Building dashboard-react image...${NC}"
    docker build -f dashboard-react/Dockerfile -t upbit-dashboard-react:latest dashboard-react/
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ dashboard-react image built successfully${NC}"
    else
        echo -e "${RED}❌ dashboard-react image build failed${NC}"
    fi
fi

echo -e "${GREEN}All images built successfully!${NC}"

# Show built images
echo -e "${YELLOW}Built images:${NC}"
docker images | grep "upbit-"

echo -e "${GREEN}Docker build completed!${NC}"