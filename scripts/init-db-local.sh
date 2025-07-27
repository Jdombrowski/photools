#!/bin/bash
# Initialize database for local development
# Runs Alembic migrations against local PostgreSQL instance

set -e

echo "🗄️ Initializing local database..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "   Run: make setup-env"
    exit 1
fi

# Source environment variables
source .env

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
max_attempts=30
attempt=0

while ! docker compose -f docker-compose.dev.yml exec -T postgres pg_isready -U ${POSTGRES_USER:-photo_user} -d ${POSTGRES_DB:-photo_catalog} > /dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "❌ PostgreSQL is not responding after $max_attempts attempts"
        echo "   Make sure infrastructure is running: ./scripts/dev-start.sh"
        exit 1
    fi
    echo "   Attempt $attempt/$max_attempts..."
    sleep 2
done

echo "✅ PostgreSQL is ready!"
echo ""

# Run database migrations
echo "🔄 Running database migrations..."
.venv/bin/python -m alembic upgrade head

echo ""
echo "✅ Database initialization completed!"
echo ""
echo "📊 Database connection details:"
echo "  🐘 Host:     localhost:${POSTGRES_PORT:-5432}"
echo "  📚 Database: ${POSTGRES_DB:-photo_catalog}"
echo "  👤 User:     ${POSTGRES_USER:-photo_user}"
echo ""
echo "🔧 Next steps:"
echo "  1. Start API server:       ./scripts/run-api.sh"
echo "  2. Start Celery worker:    ./scripts/run-worker.sh"