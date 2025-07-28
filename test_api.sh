#!/bin/bash
# API Testing Script for Photools

API_BASE="http://localhost:8000"
API_V1="${API_BASE}/api/v1"

echo "🔍 Testing Photools API..."
echo "================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to test endpoint
test_endpoint() {
    local method=$1
    local endpoint=$2
    local description=$3
    local data=$4
    
    echo -e "\n${YELLOW}Testing:${NC} $description"
    echo "→ $method $endpoint"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "HTTPSTATUS:%{http_code}" "$endpoint")
    elif [ "$method" = "POST" ] && [ -n "$data" ]; then
        response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST -H "Content-Type: application/json" -d "$data" "$endpoint")
    else
        response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X "$method" "$endpoint")
    fi
    
    http_code=$(echo $response | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    body=$(echo $response | sed -e 's/HTTPSTATUS:.*//g')
    
    if [ "$http_code" -eq 200 ]; then
        echo -e "${GREEN}✅ SUCCESS${NC} (HTTP $http_code)"
        echo "$body" | jq . 2>/dev/null || echo "$body"
    else
        echo -e "${RED}❌ FAILED${NC} (HTTP $http_code)"
        echo "$body"
    fi
}

# Test if API is running
echo "🏥 Checking if API is running..."
if curl -s "$API_BASE" > /dev/null; then
    echo -e "${GREEN}✅ API is responding${NC}"
else
    echo -e "${RED}❌ API is not responding${NC}"
    echo "Make sure the API is running with: make dev"
    exit 1
fi

# Test endpoints
test_endpoint "GET" "$API_BASE" "Root endpoint"
test_endpoint "GET" "$API_V1/health" "Basic health check"
test_endpoint "GET" "$API_V1/health/detailed" "Detailed health check"
test_endpoint "GET" "$API_V1/photos" "List photos (empty)"
test_endpoint "GET" "$API_V1/photos?limit=10&offset=0" "List photos with pagination"
test_endpoint "GET" "$API_V1/photos/test-photo-id" "Get specific photo (should 404)"
test_endpoint "POST" "$API_V1/photos/import-directory?directory_path=./data" "Import photos from directory" '{"import_options": {"priority": "HIGH"}}'
test_endpoint "GET" "$API_V1/photos" "List photos after import (should not be empty)"
test_endpoint "DELETE" "$API_V1/photos/1" "Delete specific photo (should 404)"

# Test directory scanning (use a safe directory)
test_endpoint "POST" "$API_V1/photos/scan-directory?directory_path=/tmp" "Scan directory"

echo -e "\n${GREEN}🎉 API testing complete!${NC}"
echo "View API documentation at: $API_BASE/docs"
