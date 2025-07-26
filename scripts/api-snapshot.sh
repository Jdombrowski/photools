#!/bin/bash

# API Snapshot Generation Script
# Creates baseline snapshots for API endpoints

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
API_BASE="http://localhost:8090"
SNAPSHOT_DIR="tests/snapshots/api"

# Create snapshot directory if it doesn't exist
mkdir -p "$SNAPSHOT_DIR"

echo -e "${BLUE}📸 Generating API response snapshots...${NC}"
echo ""

# Function to capture endpoint
capture_endpoint() {
    local name="$1"
    local url="$2"
    local filename="$3"
    
    echo -e "${BLUE}📊 Capturing ${name}...${NC}"
    
    if curl -s -f "$url" > "$SNAPSHOT_DIR/$filename"; then
        echo -e "${GREEN}✅ Saved to $SNAPSHOT_DIR/$filename${NC}"
    else
        echo -e "${RED}❌ Failed to capture ${name}${NC}"
        return 1
    fi
}

# Capture core endpoints that are working
capture_endpoint "Health Check" "$API_BASE/api/v1/health" "health.json"
capture_endpoint "API Root" "$API_BASE/api" "api_root.json"

# Note: These endpoints are commented out until they're working
# capture_endpoint "Photo Listing" "$API_BASE/api/v1/photos?limit=10" "photos_list.json"
# capture_endpoint "Storage Info" "$API_BASE/api/v1/storage/info" "storage_info.json"
# capture_endpoint "Preview Stats" "$API_BASE/api/v1/storage/preview-stats" "preview_stats.json"

echo ""
echo -e "${GREEN}✅ Snapshots updated!${NC}"
echo -e "${BLUE}📁 Snapshots saved in: $SNAPSHOT_DIR${NC}"
echo ""
echo -e "${BLUE}💡 Next steps:${NC}"
echo -e "   • Run 'make test-api-diff' to compare future changes"
echo -e "   • Commit snapshots to version control"
echo ""