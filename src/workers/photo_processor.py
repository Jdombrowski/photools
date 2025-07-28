import hashlib
import logging
import os
from datetime import datetime
from typing import Any

import PIL.Image
from celery import Task

from .celery_app import celery_app

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """Custom task class that can handle callbacks."""

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"Task {task_id} succeeded with result: {retval}")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {task_id} failed: {exc}")


@celery_app.task(base=CallbackTask, bind=True)
def process_single_photo(self, file_path: str) -> dict[str, Any] | None:
    """Process a single photo file and extract metadata."""
    try:
        # Validate file exists and is accessible
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get basic file information
        file_stats = os.stat(file_path)
        file_size = file_stats.st_size

        # Generate file hash for deduplication
        file_hash = generate_file_hash(file_path)

        # Extract basic image metadata using PIL
        image_metadata = extract_image_metadata(file_path)

        # Prepare result
        result = {
            "file_path": file_path,
            "file_hash": file_hash,
            "file_size": file_size,
            "created_at": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
            "processed_at": datetime.utcnow().isoformat(),
            "metadata": image_metadata,
            "status": "completed",
        }

        logger.info(f"Successfully processed photo: {file_path}")
        return result

    except Exception as e:
        logger.error(f"Error processing photo {file_path}: {str(e)}")
        self.retry(countdown=60, max_retries=3)


@celery_app.task(base=CallbackTask)
def process_batch_photos(file_paths: list) -> dict[str, Any]:
    """Process multiple photos in batch."""
    results = {"total": len(file_paths), "successful": 0, "failed": 0, "results": []}

    for file_path in file_paths:
        try:
            # Queue individual photo processing
            task_result = process_single_photo.delay(file_path)
            results["results"].append(
                {"file_path": file_path, "task_id": task_result.id, "status": "queued"}
            )
            results["successful"] += 1

        except Exception as e:
            logger.error(f"Failed to queue photo {file_path}: {str(e)}")
            results["results"].append(
                {"file_path": file_path, "status": "failed", "error": str(e)}
            )
            results["failed"] += 1

    return results


@celery_app.task(base=CallbackTask)
def scan_directory(directory_path: str, recursive: bool = True) -> dict[str, Any]:
    """Scan a directory for photo files."""
    photo_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".tiff",
        ".tif",
        ".raw",
        ".cr2",
        ".nef",
        ".arw",
        ".heic",
    }
    found_photos = []

    try:
        if recursive:
            for root, dirs, files in os.walk(directory_path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for file in files:
                    if not file.startswith("."):  # Skip hidden files
                        file_path = os.path.join(root, file)
                        _, ext = os.path.splitext(file.lower())

                        if ext in photo_extensions:
                            found_photos.append(file_path)
        else:
            # Scan only the specified directory
            for file in os.listdir(directory_path):
                file_path = os.path.join(directory_path, file)
                if os.path.isfile(file_path) and not file.startswith("."):
                    _, ext = os.path.splitext(file.lower())
                    if ext in photo_extensions:
                        found_photos.append(file_path)

        result = {
            "directory": directory_path,
            "recursive": recursive,
            "total_photos": len(found_photos),
            "photos": found_photos,
            "scanned_at": datetime.utcnow().isoformat(),
            "status": "completed",
        }

        logger.info(
            f"Directory scan completed: {directory_path} - "
            f"Found {len(found_photos)} photos"
        )
        return result

    except Exception as e:
        logger.error(f"Error scanning directory {directory_path}: {str(e)}")
        raise


def generate_file_hash(file_path: str) -> str:
    """Generate SHA-256 hash of file for deduplication."""
    hash_sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)

    return hash_sha256.hexdigest()


@celery_app.task(base=CallbackTask, bind=True)
def generate_preview_task(
    self,
    photo_id: str,
    storage_path: str,
    filename: str,
    priority: str = "normal",
    requested_sizes: list = None,
) -> dict[str, Any]:
    """Generate preview(s) for a photo with priority-aware execution.

    Args:
        photo_id: Photo identifier
        storage_path: Path to original file in storage
        filename: Original filename
        priority: urgent|high|normal|low (affects routing and execution)
        requested_sizes: List of specific sizes to generate, or None for all

    """
    from pathlib import Path

    from src.core.services.photo_upload_service import PhotoUploadService
    from src.core.services.preview_generator import PreviewGenerator, PreviewSize

    # Set task priority metadata for monitoring
    if requested_sizes is None:
        requested_sizes = []
    self.update_state(
        state="PROGRESS",
        meta={"priority": priority, "photo_id": photo_id, "stage": "starting"},
    )

    try:
        # Initialize services
        preview_generator = PreviewGenerator()
        upload_service = PhotoUploadService()

        # Construct full storage path
        full_storage_path = Path(upload_service.storage.config.base_path) / storage_path

        if not full_storage_path.exists():
            return {
                "photo_id": photo_id,
                "success": False,
                "error": f"Source file not found: {full_storage_path}",
                "priority": priority,
            }

        # Determine which sizes to generate
        if requested_sizes:
            sizes_to_generate = [
                PreviewSize(size)
                for size in requested_sizes
                if size in [s.value for s in PreviewSize]
            ]
        else:
            sizes_to_generate = list(PreviewSize)

        # For urgent requests, check what already exists to minimize work
        if priority == "urgent":
            existing_previews = preview_generator.get_preview_info(photo_id)
            # Only generate missing sizes for urgent requests
            sizes_to_generate = [
                size
                for size in sizes_to_generate
                if size.value not in existing_previews
            ]

        self.update_state(
            state="PROGRESS",
            meta={
                "priority": priority,
                "photo_id": photo_id,
                "stage": "generating",
                "sizes_count": len(sizes_to_generate),
            },
        )

        # Generate previews
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            if requested_sizes and len(requested_sizes) == 1:
                # Single size request - generate immediately
                size = PreviewSize(requested_sizes[0])
                result_path = loop.run_until_complete(
                    preview_generator.generate_preview(
                        full_storage_path, photo_id, size
                    )
                )
                results = {size.value: result_path}
            else:
                # Multiple sizes - generate all requested
                if sizes_to_generate:
                    # Generate only requested/missing sizes
                    results = {}
                    for size in sizes_to_generate:
                        result_path = loop.run_until_complete(
                            preview_generator.generate_preview(
                                full_storage_path, photo_id, size
                            )
                        )
                        results[size.value] = result_path
                else:
                    # All sizes already exist
                    results = {}

            successful_previews = {
                size: str(path) if path else None
                for size, path in results.items()
                if path
            }

            return {
                "photo_id": photo_id,
                "success": True,
                "generated_previews": successful_previews,
                "total_generated": len(successful_previews),
                "priority": priority,
                "execution_time": getattr(self.request, "time_start", None),
            }

        finally:
            loop.close()

    except Exception as e:
        logger.error(
            f"Preview generation failed for {photo_id} (priority: {priority}): {e}"
        )
        return {
            "photo_id": photo_id,
            "success": False,
            "error": str(e),
            "priority": priority,
        }


@celery_app.task(base=CallbackTask)
def bulk_generate_previews_task(batch_size: int = 10) -> dict[str, Any]:
    """Generate previews for all photos that don't have them."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from src.config.settings import get_settings
    from src.core.services.preview_generator import PreviewGenerator
    from src.infrastructure.database.models import Photo

    settings = get_settings()
    engine = create_engine(settings.database.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    try:
        with SessionLocal() as db:
            # Get photos that need preview generation
            stmt = select(Photo).limit(batch_size)
            result = db.execute(stmt)
            photos = result.scalars().all()

            if not photos:
                return {
                    "success": True,
                    "message": "No photos found to process",
                    "processed": 0,
                }

            # Initialize preview generator
            preview_generator = PreviewGenerator()

            processed_count = 0
            errors = []

            for photo in photos:
                try:
                    # Check if photo already has previews
                    existing_previews = preview_generator.get_preview_info(
                        str(photo.id)
                    )

                    # Skip if all preview sizes exist
                    if len(existing_previews) >= 4:  # All 4 sizes
                        continue

                    # Queue individual preview generation task
                    generate_preview_task.delay(
                        photo.id, photo.file_path, photo.filename
                    )
                    processed_count += 1

                except Exception as e:
                    logger.error(
                        f"Failed to queue preview generation for {photo.id}: {e}"
                    )
                    errors.append(f"Photo {photo.id}: {str(e)}")

            return {
                "success": True,
                "processed": processed_count,
                "total_photos": len(photos),
                "errors": errors,
            }

    except Exception as e:
        logger.error(f"Bulk preview generation failed: {e}")
        return {"success": False, "error": str(e)}


def extract_image_metadata(file_path: str) -> dict[str, Any]:
    """Extract basic image metadata using PIL."""
    try:
        with PIL.Image.open(file_path) as img:
            # Basic image info
            metadata = {
                "format": img.format,
                "mode": img.mode,
                "size": img.size,
                "width": img.width,
                "height": img.height,
            }

            # Try to get EXIF data
            if hasattr(img, "_getexif") and img._exif is not None:
                exif_data = img._exif
                if exif_data:
                    metadata["exif_available"] = True
                    metadata["exif_tags_count"] = len(exif_data)

                    # Extract some common EXIF tags
                    # Note: In production, use ExifRead or similar for
                    # comprehensive EXIF parsing
                    try:
                        if 306 in exif_data:  # DateTime
                            metadata["datetime"] = str(exif_data[306])
                        if 271 in exif_data:  # Make
                            metadata["camera_make"] = str(exif_data[271])
                        if 272 in exif_data:  # Model
                            metadata["camera_model"] = str(exif_data[272])
                    except Exception as e:
                        logger.warning(f"Error extracting specific EXIF data: {str(e)}")
                else:
                    metadata["exif_available"] = False
            else:
                metadata["exif_available"] = False

            return metadata

    except Exception as e:
        logger.error(f"Error extracting metadata from {file_path}: {str(e)}")
        return {
            "error": str(e),
            "format": "unknown",
            "metadata_extraction_failed": True,
        }
