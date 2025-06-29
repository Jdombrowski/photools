#!/bin/bash

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

API_URL="http://localhost:8000"

echo -e "${BLUE}🚀 Quick Photools API Test${NC}"
echo "=============================="
echo ""

# Function to test endpoint
test_endpoint() {
    echo -e "${YELLOW}Testing: $1${NC}"
    response=$(curl -s -w "\n%{http_code}" "$API_URL$2")
    status_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n -1)
    
    if [ "$status_code" -eq 200 ]; then
        echo -e "${GREEN}✅ SUCCESS${NC} (HTTP $status_code)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
    else
        echo -e "${RED}❌ FAILED${NC} (HTTP $status_code)"
        echo "$body"
    fi
    echo ""
}

# Quick tests
test_endpoint "Root Endpoint" "/"
test_endpoint "Health Check" "/health"
test_endpoint "API Info" "/info"
test_endpoint "Database Health" "/health/db"
test_endpoint "Redis Health" "/health/redis"

echo -e "${BLUE}🔧 Quick Commands:${NC}"
echo "===================="
echo ""
echo "# View API documentation:"
echo "open http://localhost:8000/docs"
echo ""
echo "# Test with curl:"
echo "curl -s http://localhost:8000/health | jq"
echo ""
echo "# Connect to database:"
echo "make db-shell"
echo ""
echo "# View API logs:"
echo "make docker-logs-api"
echo ""
echo "# View all service logs:"
echo "make docker-logs"