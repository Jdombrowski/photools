import os

from celery import Celery

# Get Redis URL from environment or use default
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery instance
celery_app = Celery(
    "photools",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["src.workers.photo_processor", "src.workers.model_indexer"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task routing
    task_routes={
        "src.workers.photo_processor.*": {"queue": "photo_processing"},
        "src.workers.model_indexer.*": {"queue": "ai_processing"},
    },
    # Worker configuration
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    # Task time limits
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,  # 10 minutes
    # Result backend settings
    result_expires=3600,  # 1 hour
    # Beat schedule (for periodic tasks)
    beat_schedule={},
)

if __name__ == "__main__":
    celery_app.start()
