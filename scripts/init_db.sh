#!/bin/bash
# Simple database initialization script

echo "🚀 Initializing database..."

# Run Alembic migrations to latest
echo "📊 Running database migrations..."
poetry run alembic upgrade head

if [ $? -eq 0 ]; then
    echo "✅ Database initialized successfully!"
else
    echo "❌ Database initialization failed!"
    exit 1
fi


