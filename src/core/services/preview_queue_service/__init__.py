import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Union

logger = logging.getLogger(__name__)


class PreviewPriority(Enum):
    """Preview generation priority levels."""

    URGENT = "urgent"  # User-requested immediate need
    HIGH = "high"  # Recently uploaded photos
    NORMAL = "normal"  # Bulk generation, background processing
    LOW = "low"  # Maintenance tasks, cleanup


@dataclass
class PreviewRequest:
    """Represents a preview generation request."""

    photo_id: str
    storage_path: str
    filename: str
    priority: PreviewPriority
    requested_sizes: list[str] | None = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class PreviewQueueService:
    """Smart priority-based queueing service for preview generation.

    Features:
    - Priority-aware task routing
    - Duplicate detection and consolidation
    - Queue inspection and management
    - Adaptive execution based on system load
    """

    def __init__(self):
        self.active_tasks = {}  # Track active tasks to avoid duplicates

    def queue_preview_generation(
        self,
        photo_id: str,
        storage_path: str,
        filename: str,
        priority: PreviewPriority | str = PreviewPriority.NORMAL,
        requested_sizes: list[str] | None = None,
        force_queue: bool = False,
    ) -> dict:
        """Queue a preview generation task with smart priority handling.

        Args:
            photo_id: Photo identifier
            storage_path: Path to original file
            filename: Original filename
            priority: Priority level for execution
            requested_sizes: Specific preview sizes needed
            force_queue: Skip duplicate detection

        Returns:
            Dict with task information and status

        """
        from src.workers.photo_processor import generate_preview_task

        # Normalize priority
        if isinstance(priority, str):
            priority = PreviewPriority(priority.lower())

        # Check for existing active tasks unless forced
        if not force_queue:
            existing_task = self._check_existing_task(photo_id, requested_sizes)
            if existing_task:
                return {
                    "status": "existing",
                    "message": f"Task already active for photo {photo_id}",
                    "existing_task_id": existing_task["task_id"],
                    "existing_priority": existing_task["priority"],
                }

        # For urgent requests, try to cancel lower priority tasks for same photo
        if priority == PreviewPriority.URGENT:
            self._cancel_lower_priority_tasks(photo_id)

        # Determine queue routing based on priority
        queue_options = self._get_queue_options(priority)

        try:
            # Queue the task with priority-specific options
            task = generate_preview_task.apply_async(
                args=[
                    photo_id,
                    storage_path,
                    filename,
                    priority.value,
                    requested_sizes,
                ],
                **queue_options,
            )

            # Track the active task
            self._track_active_task(photo_id, task.id, priority, requested_sizes)

            return {
                "status": "queued",
                "task_id": task.id,
                "photo_id": photo_id,
                "priority": priority.value,
                "requested_sizes": requested_sizes,
                "queue_position": self._estimate_queue_position(priority),
                "estimated_wait_seconds": self._estimate_wait_time(priority),
            }

        except Exception as e:
            logger.error(f"Failed to queue preview generation for {photo_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "photo_id": photo_id,
                "priority": priority.value,
            }

    def queue_urgent_preview(
        self, photo_id: str, storage_path: str, filename: str, size: str
    ) -> dict:
        """Quick method for urgent single-size preview requests.

        Optimized for immediate user needs - checks existing previews
        and only generates what's actually missing.
        """
        from src.core.services.preview_generator import PreviewGenerator

        # Check if preview already exists
        preview_generator = PreviewGenerator()
        existing_preview = preview_generator.get_preview_info(photo_id)

        if size in existing_preview:
            return {
                "status": "exists",
                "message": f"Preview {size} already exists for photo {photo_id}",
                "photo_id": photo_id,
                "size": size,
            }

        # Queue urgent generation for just this size
        return self.queue_preview_generation(
            photo_id=photo_id,
            storage_path=storage_path,
            filename=filename,
            priority=PreviewPriority.URGENT,
            requested_sizes=[size],
        )

    def _check_existing_task(
        self, photo_id: str, requested_sizes: list[str] | None
    ) -> dict | None:
        """Check if there's already an active task for this photo/sizes combination."""
        if photo_id not in self.active_tasks:
            return None

        task_info = self.active_tasks[photo_id]

        # If no specific sizes requested, any active task counts
        if not requested_sizes:
            return task_info

        # Check if requested sizes overlap with active task
        active_sizes = task_info.get("requested_sizes")
        if not active_sizes:  # Active task is generating all sizes
            return task_info

        # Check for overlap in requested sizes
        if set(requested_sizes) & set(active_sizes):
            return task_info

        return None

    def _cancel_lower_priority_tasks(self, photo_id: str):
        """Cancel lower priority tasks for the same photo when urgent request comes in."""
        if photo_id not in self.active_tasks:
            return

        task_info = self.active_tasks[photo_id]
        current_priority = PreviewPriority(task_info["priority"])

        # Only cancel if current task is lower priority than urgent
        if current_priority != PreviewPriority.URGENT:
            try:
                from src.workers.celery_app import celery_app

                celery_app.control.revoke(task_info["task_id"], terminate=True)
                logger.info(
                    f"Cancelled lower priority task {task_info['task_id']} for urgent request"
                )
                del self.active_tasks[photo_id]
            except Exception as e:
                logger.warning(f"Failed to cancel task {task_info['task_id']}: {e}")

    def _get_queue_options(self, priority: PreviewPriority) -> dict:
        """Get Celery queue options based on priority."""
        options = {}

        if priority == PreviewPriority.URGENT:
            options.update(
                {
                    "priority": 9,  # Highest priority
                    "queue": "preview_urgent",
                    "countdown": 0,  # Execute immediately
                }
            )
        elif priority == PreviewPriority.HIGH:
            options.update(
                {"priority": 7, "queue": "preview_high", "countdown": 1}  # Small delay
            )
        elif priority == PreviewPriority.NORMAL:
            options.update(
                {
                    "priority": 5,
                    "queue": "preview_normal",
                    "countdown": 5,  # Normal delay
                }
            )
        else:  # LOW
            options.update(
                {
                    "priority": 3,
                    "queue": "preview_low",
                    "countdown": 30,  # Longer delay for low priority
                }
            )

        return options

    def _track_active_task(
        self,
        photo_id: str,
        task_id: str,
        priority: PreviewPriority,
        requested_sizes: list[str] | None,
    ):
        """Track an active task to prevent duplicates."""
        self.active_tasks[photo_id] = {
            "task_id": task_id,
            "priority": priority.value,
            "requested_sizes": requested_sizes,
            "started_at": datetime.utcnow(),
        }

    def _estimate_queue_position(self, priority: PreviewPriority) -> int:
        """Estimate position in queue based on priority (simplified)."""
        # In real implementation, would inspect actual Celery queues
        base_positions = {
            PreviewPriority.URGENT: 1,
            PreviewPriority.HIGH: 3,
            PreviewPriority.NORMAL: 10,
            PreviewPriority.LOW: 25,
        }
        return base_positions.get(priority, 10)

    def _estimate_wait_time(self, priority: PreviewPriority) -> int:
        """Estimate wait time in seconds based on priority."""
        # In real implementation, would use historical data and current load
        base_times = {
            PreviewPriority.URGENT: 5,  # ~5 seconds
            PreviewPriority.HIGH: 15,  # ~15 seconds
            PreviewPriority.NORMAL: 60,  # ~1 minute
            PreviewPriority.LOW: 300,  # ~5 minutes
        }
        return base_times.get(priority, 60)

    def cleanup_completed_tasks(self):
        """Remove completed tasks from active tracking."""
        from src.workers.celery_app import celery_app

        completed_photos = []
        for photo_id, task_info in self.active_tasks.items():
            try:
                task_result = celery_app.AsyncResult(task_info["task_id"])
                if task_result.ready():
                    completed_photos.append(photo_id)
            except Exception as e:
                logger.warning(f"Error checking task status for {photo_id}: {e}")
                completed_photos.append(photo_id)  # Remove problematic entries

        for photo_id in completed_photos:
            del self.active_tasks[photo_id]

        return len(completed_photos)

    def get_queue_stats(self) -> dict:
        """Get current queue statistics."""
        from src.workers.celery_app import celery_app

        try:
            inspect = celery_app.control.inspect()
            active = inspect.active()
            scheduled = inspect.scheduled()

            stats = {
                "active_tasks": len(self.active_tasks),
                "celery_active": sum(len(tasks) for tasks in (active or {}).values()),
                "celery_scheduled": sum(
                    len(tasks) for tasks in (scheduled or {}).values()
                ),
                "active_by_priority": {},
            }

            # Count active tasks by priority
            for task_info in self.active_tasks.values():
                priority = task_info["priority"]
                stats["active_by_priority"][priority] = (
                    stats["active_by_priority"].get(priority, 0) + 1
                )

            return stats

        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {"error": str(e), "active_tasks": len(self.active_tasks)}


# Global instance for the application
preview_queue = PreviewQueueService()
