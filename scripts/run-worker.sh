#!/bin/bash
# Start Celery worker locally for development
# Connects to Dockerized Redis broker

set -e

echo "⚙️ Starting Photools Celery Worker (Local Development)"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "   Run: make setup-env"
    exit 1
fi

# Source environment variables
source .env

# Check if Redis is running
echo "🔍 Checking Redis connection..."

if ! docker compose -f docker-compose.dev.yml exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running"
    echo "   Start infrastructure: ./scripts/dev-start.sh"
    exit 1
fi

echo "✅ Redis is ready!"
echo ""

# Ensure required directories exist
mkdir -p ${UPLOAD_DIR:-./uploads}
mkdir -p ${MODELS_DIR:-./models}

echo "👷 Starting Celery worker..."
echo "   🔗 Broker: ${CELERY_BROKER_URL:-redis://localhost:6379/0}"
echo "   📊 Result Backend: ${CELERY_RESULT_BACKEND:-redis://localhost:6379/1}"
echo "   📝 Log Level: ${CELERY_LOG_LEVEL:-info}"
echo ""
echo "Available tasks:"
echo "   • process_single_photo"
echo "   • process_batch_photos"
echo "   • scan_directory"
echo "   • generate_preview_task"
echo "   • bulk_generate_previews_task"
echo ""
echo "Press Ctrl+C to stop the worker"
echo ""

# Start the Celery worker
.venv/bin/python -m celery -A src.workers.celery_app worker \
    --loglevel=${CELERY_LOG_LEVEL:-info} \
    --concurrency=4 \
    --prefetch-multiplier=1