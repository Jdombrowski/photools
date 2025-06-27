"""
Simple Celery Application
"""

from celery import Celery
import os

# Get configuration from environment
BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# Create Celery app
app = Celery(
    "photools",
    broker=BROKER_URL,
    backend=RESULT_BACKEND
)

# Basic configuration
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@app.task
def test_task(message: str = "Hello from Celery!"):
    """Test task to verify Celery is working"""
    return f"Task completed: {message}"

@app.task
def process_photo(photo_path: str):
    """Process photo task (placeholder)"""
    return {
        "photo_path": photo_path,
        "status": "processed",
        "message": "Photo processing - ready for implementation"
    }

if __name__ == "__main__":
    app.start()