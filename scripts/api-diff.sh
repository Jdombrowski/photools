#!/bin/bash

# API Change Detection Script
# Focuses on scannable, actionable output for quick decision-making

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
GREY='\033[0;37m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Icons for visual scanning
UNCHANGED="✅"
CHANGED="🔄"
ADDED="➕"
REMOVED="❌"
CRITICAL="🚨"

# Configuration
API_BASE="http://localhost:8090"
SNAPSHOT_DIR="tests/snapshots/api"
TEMP_DIR="/tmp/api-diff-$$"
mkdir -p "$TEMP_DIR"

# Fields to ignore during comparison (volatile data)
IGNORE_FIELDS=(
    "timestamp"
    "created_at"
    "updated_at"
    "request_id"
    "session_id"
    "current_time"
    "server_time"
)

# Track overall results
TOTAL_CHANGES=0
BREAKING_CHANGES=0
SAFE_CHANGES=0

# Function to filter out ignored fields from JSON
filter_json() {
    local input_file="$1"
    local output_file="$2"
    
    # Build jq filter to remove ignored fields at any depth
    local filter="."
    for field in "${IGNORE_FIELDS[@]}"; do
        filter="$filter | walk(if type == \"object\" then del(.$field) else . end)"
    done
    
    # Apply filter
    jq "$filter" "$input_file" > "$output_file" 2>/dev/null || cp "$input_file" "$output_file"
}

# Cleanup function
cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

# Function to detect change type and severity
analyze_change() {
    local endpoint="$1"
    local old_file="$2"
    local new_file="$3"
    
    # Create filtered versions for comparison
    local old_filtered="$TEMP_DIR/old_filtered.json"
    local new_filtered="$TEMP_DIR/new_filtered.json"
    
    filter_json "$old_file" "$old_filtered"
    filter_json "$new_file" "$new_filtered"
    
    # Skip if filtered files are identical (no structural changes)
    if cmp -s "$old_filtered" "$new_filtered"; then
        return 0
    fi
    
    TOTAL_CHANGES=$((TOTAL_CHANGES + 1))
    
    # Parse filtered JSON and look for structural changes
    local old_keys=$(jq -r 'paths(scalars) as $p | $p | join(".")' "$old_filtered" 2>/dev/null | sort | uniq)
    local new_keys=$(jq -r 'paths(scalars) as $p | $p | join(".")' "$new_filtered" 2>/dev/null | sort | uniq)
    
    # Find added/removed keys
    local added_keys=$(comm -13 <(echo "$old_keys") <(echo "$new_keys"))
    local removed_keys=$(comm -23 <(echo "$old_keys") <(echo "$new_keys"))
    
    # Determine severity
    local severity="SAFE"
    local icon="$CHANGED"
    
    if [[ -n "$removed_keys" ]]; then
        severity="BREAKING"
        icon="$CRITICAL"
        BREAKING_CHANGES=$((BREAKING_CHANGES + 1))
    elif [[ -n "$added_keys" ]]; then
        severity="SAFE"
        icon="$ADDED"
        SAFE_CHANGES=$((SAFE_CHANGES + 1))
    else
        # Value changes only
        severity="SAFE"
        icon="$CHANGED"
        SAFE_CHANGES=$((SAFE_CHANGES + 1))
    fi
    
    # Color based on severity
    local color="$GREEN"
    if [[ "$severity" == "BREAKING" ]]; then
        color="$RED"
    elif [[ "$severity" == "SAFE" ]]; then
        color="$GREY"
    fi
    
    echo -e "${color}${icon} ${endpoint}${NC}"
    
    # Show key structural changes
    if [[ -n "$removed_keys" ]]; then
        echo -e "  ${RED}${REMOVED} Removed fields:${NC}"
        echo "$removed_keys" | while read -r key; do
            [[ -n "$key" ]] && echo -e "    ${RED}• $key${NC}"
        done
    fi
    
    if [[ -n "$added_keys" ]]; then
        echo -e "  ${GREEN}${ADDED} Added fields:${NC}"
        echo "$added_keys" | while read -r key; do
            [[ -n "$key" ]] && echo -e "    ${GREEN}• $key${NC}"
        done
    fi
    
    # Show sample value changes for important fields (using filtered data)
    if [[ -z "$removed_keys" && -z "$added_keys" ]]; then
        echo -e "  ${BLUE}📝 Value changes detected (ignoring timestamps)${NC}"
        
        # Show specific important changes using filtered data
        local old_count=$(jq -r '.photos | length // .total // empty' "$old_filtered" 2>/dev/null)
        local new_count=$(jq -r '.photos | length // .total // empty' "$new_filtered" 2>/dev/null)
        
        if [[ -n "$old_count" && -n "$new_count" && "$old_count" != "$new_count" ]]; then
            echo -e "    ${BLUE}• Count: $old_count → $new_count${NC}"
        fi
        
        # Show version changes
        local old_version=$(jq -r '.version // empty' "$old_filtered" 2>/dev/null)
        local new_version=$(jq -r '.version // empty' "$new_filtered" 2>/dev/null)
        
        if [[ -n "$old_version" && -n "$new_version" && "$old_version" != "$new_version" ]]; then
            echo -e "    ${BLUE}• Version: $old_version → $new_version${NC}"
        fi
    fi
    
    echo ""
}

# Function to test endpoint and compare
test_endpoint() {
    local name="$1"
    local url="$2"
    local snapshot_file="$3"
    
    if [[ ! -f "$SNAPSHOT_DIR/$snapshot_file" ]]; then
        echo -e "${GREY}⚠️  No snapshot for $name${NC}"
        return
    fi
    
    # Fetch current response
    local current_file="$TEMP_DIR/$snapshot_file"
    if ! curl -s -f "$url" > "$current_file"; then
        echo -e "${RED}❌ Failed to fetch $name${NC}"
        return
    fi
    
    # Analyze changes
    analyze_change "$name" "$SNAPSHOT_DIR/$snapshot_file" "$current_file"
}

# Header
echo -e "${CYAN}🔍 API Change Detection Report${NC}"
echo -e "${CYAN}═══════════════════════════════${NC}"
echo -e "${GREY}Ignoring volatile fields: ${IGNORE_FIELDS[*]}${NC}"
echo ""

# Test core endpoints
test_endpoint "Health Check" "$API_BASE/api/v1/health" "health.json"
test_endpoint "API Root" "$API_BASE/api" "api_root.json"
# Note: Photos endpoint temporarily disabled due to database setup
# test_endpoint "Photo Listing" "$API_BASE/api/v1/photos?limit=10" "photos_list.json"
# test_endpoint "Storage Info" "$API_BASE/api/v1/storage/info" "storage_info.json"
# test_endpoint "Preview Stats" "$API_BASE/api/v1/storage/preview-stats" "preview_stats.json"

# Summary
echo -e "${CYAN}📊 Summary${NC}"
echo -e "${CYAN}═══════════${NC}"

if [[ $TOTAL_CHANGES -eq 0 ]]; then
    echo -e "${GREEN}${UNCHANGED} No changes detected${NC}"
    echo -e "${GREEN}✅ APIs are stable${NC}"
else
    echo -e "${BLUE}📈 Total changes: $TOTAL_CHANGES${NC}"
    
    if [[ $BREAKING_CHANGES -gt 0 ]]; then
        echo -e "${RED}${CRITICAL} Breaking changes: $BREAKING_CHANGES${NC}"
        echo -e "${RED}🔍 REQUIRES ATTENTION${NC}"
    fi
    
    if [[ $SAFE_CHANGES -gt 0 ]]; then
        echo -e "${GREY}${ADDED} Safe changes: $SAFE_CHANGES${NC}"
    fi
fi

echo ""

# Decision helper
echo -e "${PURPLE}🤔 Decision Tree:${NC}"
if [[ $BREAKING_CHANGES -gt 0 ]]; then
    echo -e "${RED}1. Breaking changes detected${NC}"
    echo -e "${RED}2. Review changes above${NC}"
    echo -e "${RED}3. Update API version if needed${NC}"
    echo -e "${RED}4. Update documentation${NC}"
    echo -e "${RED}5. Consider migration strategy${NC}"
elif [[ $SAFE_CHANGES -gt 0 ]]; then
    echo -e "${GREY}1. Safe changes detected${NC}"
    echo -e "${GREY}2. Review if changes are expected${NC}"
    echo -e "${GREY}3. Update snapshots if intentional${NC}"
    echo -e "${GREEN}   → make test-api-snapshot${NC}"
else
    echo -e "${GREEN}1. No changes detected${NC}"
    echo -e "${GREEN}2. APIs are stable${NC}"
fi

echo ""

# Exit with appropriate code
if [[ $BREAKING_CHANGES -gt 0 ]]; then
    echo -e "${RED}❌ Breaking changes require attention${NC}"
    exit 1
elif [[ $SAFE_CHANGES -gt 0 ]]; then
    echo -e "${GREY}⚠️  Safe changes detected${NC}"
    exit 2
else
    echo -e "${GREEN}✅ No changes detected${NC}"
    exit 0
fi