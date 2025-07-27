#!/bin/bash
# Start FastAPI server locally for development
# Connects to Dockerized PostgreSQL and Redis

set -e

echo "🚀 Starting Photools API Server (Local Development)"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "   Run: make setup-env"
    exit 1
fi

# Source environment variables
source .env

# Check if infrastructure services are running
echo "🔍 Checking infrastructure services..."

if ! docker compose -f docker-compose.dev.yml exec -T postgres pg_isready -U ${POSTGRES_USER:-photo_user} -d ${POSTGRES_DB:-photo_catalog} > /dev/null 2>&1; then
    echo "❌ PostgreSQL is not running"
    echo "   Start infrastructure: ./scripts/dev-start.sh"
    exit 1
fi

if ! docker compose -f docker-compose.dev.yml exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running"
    echo "   Start infrastructure: ./scripts/dev-start.sh" 
    exit 1
fi

echo "✅ Infrastructure services are ready!"
echo ""

# Ensure uploads directory exists
mkdir -p ${UPLOAD_DIR:-./uploads}

echo "🌐 Starting FastAPI server..."
echo "   📍 URL: http://localhost:${API_PORT:-8090}"
echo "   📖 Docs: http://localhost:${API_PORT:-8090}/docs"
echo "   🔄 Auto-reload: Enabled"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the API server with auto-reload
.venv/bin/python -m uvicorn src.api.main:app \
    --host ${API_HOST:-0.0.0.0} \
    --port ${API_PORT:-8090} \
    --reload \
    --reload-dir src