import hashlib
import logging
import os
from datetime import datetime
from typing import Any, Dict

from celery import Task
from PIL import Image

from .celery_app import celery_app

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """Custom task class that can handle callbacks"""

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"Task {task_id} succeeded with result: {retval}")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {task_id} failed: {exc}")


@celery_app.task(base=CallbackTask, bind=True)
def process_single_photo(self, file_path: str) -> Dict[str, Any]:
    """Process a single photo file and extract metadata"""

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
def process_batch_photos(file_paths: list) -> Dict[str, Any]:
    """Process multiple photos in batch"""

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
def scan_directory(directory_path: str, recursive: bool = True) -> Dict[str, Any]:
    """Scan a directory for photo files"""

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
            f"Directory scan completed: {directory_path} - Found {len(found_photos)} photos"
        )
        return result

    except Exception as e:
        logger.error(f"Error scanning directory {directory_path}: {str(e)}")
        raise


def generate_file_hash(file_path: str) -> str:
    """Generate SHA-256 hash of file for deduplication"""
    hash_sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)

    return hash_sha256.hexdigest()


def extract_image_metadata(file_path: str) -> Dict[str, Any]:
    """Extract basic image metadata using PIL"""

    try:
        with Image.open(file_path) as img:
            # Basic image info
            metadata = {
                "format": img.format,
                "mode": img.mode,
                "size": img.size,
                "width": img.width,
                "height": img.height,
            }

            # Try to get EXIF data
            if hasattr(img, "_getexif") and img._getexif() is not None:
                exif_data = img._getexif()
                if exif_data:
                    metadata["exif_available"] = True
                    metadata["exif_tags_count"] = len(exif_data)

                    # Extract some common EXIF tags
                    # Note: In production, use ExifRead or similar for comprehensive EXIF parsing
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
 
