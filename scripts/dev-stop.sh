#!/bin/bash
# Stop local development infrastructure services

set -e

echo "🛑 Stopping Photools Local Development Infrastructure"
echo ""

# Stop infrastructure services
echo "📦 Stopping infrastructure services (PostgreSQL + Redis)..."
docker compose -f docker-compose.dev.yml down

echo ""
echo "✅ Infrastructure services stopped!"
echo ""
echo "💡 Note: API and Celery workers (if running locally) need to be stopped manually with Ctrl+C"