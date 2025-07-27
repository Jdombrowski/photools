#!/bin/bash
# Local Development Startup Script
# Starts infrastructure and provides commands to run API and workers locally

set -e

echo "🚀 Starting Photools Local Development Environment"
echo ""

# Start infrastructure services
echo "📦 Starting infrastructure services (PostgreSQL + Redis)..."
docker compose -f docker-compose.dev.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check service health
echo "🔍 Checking service health..."
docker compose -f docker-compose.dev.yml ps

echo ""
echo "✅ Infrastructure services are running!"
echo ""
echo "🔧 Next steps:"
echo "  1. Initialize database:    ./scripts/init-db-local.sh"
echo "  2. Start API server:       ./scripts/run-api.sh"
echo "  3. Start Celery worker:    ./scripts/run-worker.sh"
echo ""
echo "📊 Service URLs:"
echo "  🐘 PostgreSQL: localhost:5432"
echo "  🔴 Redis:      localhost:6379"
echo "  🌐 API:        http://localhost:8090 (when started)"
echo "  📖 API Docs:   http://localhost:8090/docs (when started)"
echo ""
echo "🛑 To stop infrastructure: docker compose -f docker-compose.dev.yml down"