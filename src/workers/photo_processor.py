import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from celery import Task
from PIL import Image

from src.core.services.directory_scanner import SecureDirectoryScanner
from src.core.services.file_system_service import SecureFileSystemService
from src.core.services.photo_import_service import ImportOptions, PhotoImportService
from src.core.services.photo_upload_service import PhotoUploadService
from src.core.storage import LocalStorageBackend, StorageConfig
from src.infrastructure.database.connection import DatabaseManager
from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Global service instances to avoid repeated initialization
_photo_upload_service: PhotoUploadService | None = None
_storage_backend: LocalStorageBackend | None = None


def get_photo_upload_service() -> PhotoUploadService:
    """Get or create photo upload service singleton."""
    global _photo_upload_service, _storage_backend

    if _photo_upload_service is None:
        # Create storage backend
        storage_config = StorageConfig(
            base_path=Path("./uploads").resolve(),
            organize_by_date=True,
            use_content_hash=True,
        )
        _storage_backend = LocalStorageBackend(storage_config)
        _photo_upload_service = PhotoUploadService(_storage_backend)

    return _photo_upload_service


def create_photo_import_service(allowed_directories: list[Path]) -> PhotoImportService:
    """Create PhotoImportService with required dependencies."""
    # Create file system service
    file_system_service = SecureFileSystemService.create_readonly_photo_service(
        allowed_directories
    )

    # Create directory scanner
    directory_scanner = SecureDirectoryScanner(file_system_service)

    # Get shared services
    photo_upload_service = get_photo_upload_service()

    # Ensure storage backend is available
    if _storage_backend is None:
        get_photo_upload_service()  # This will initialize _storage_backend
    assert (
        _storage_backend is not None
    ), "Storage backend must be initialized before creating PhotoImportService"

    return PhotoImportService(
        directory_scanner=directory_scanner,
        photo_upload_service=photo_upload_service,
        storage_backend=_storage_backend,
    )


class PhotoImportTask(Task):
    """Custom task class for photo import operations with progress tracking."""

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"Photo import task {task_id} succeeded: {retval.get('status')}")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Photo import task {task_id} failed: {exc}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(f"Photo import task {task_id} retrying: {exc}")


@celery_app.task(base=PhotoImportTask, bind=True)
def process_single_photo(self, file_path: str) -> dict[str, Any]:
    """Process a single photo file using PhotoImportService architecture."""
    try:

        # Convert string path to Path object
        path_obj = Path(file_path)

        # Validate file exists and is accessible
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:

            async def import_photo():
                # Get database session
                database_manager = DatabaseManager()

                async with database_manager.get_async_session() as session:
                    # Create PhotoImportService efficiently using factory
                    import_service = create_photo_import_service([path_obj.parent])

                    # Configure import options for single photo processing
                    options = ImportOptions(
                        skip_duplicates=True,
                        extract_metadata=True,
                        progress_callback=None,  # No callback for Celery tasks
                    )

                    # Import single photo using the service
                    result = await import_service.import_single_photo(
                        path_obj, session, options
                    )

                    return result

            # Run the async import
            import_result = loop.run_until_complete(import_photo())

            # Convert ImportResult to dict format expected by Celery
            return {
                "status": import_result.status,
                "file_path": file_path,
                "import_id": import_result.import_id,
                "source_directory": import_result.source_directory,
                # Summary counts
                "total_files": import_result.total_files,
                "imported_files": import_result.imported_files,
                "skipped_files": import_result.skipped_files,
                "failed_files": import_result.failed_files,
                # Timing
                "start_time": (
                    import_result.start_time.isoformat()
                    if import_result.start_time
                    else None
                ),
                "end_time": datetime.now(UTC).isoformat(),
            }

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Error processing photo {file_path}: {str(e)}")

        # Check if we should retry
        if self.request.retries < 3:
            self.retry(countdown=60, max_retries=3)
            # This line never executes due to retry exception, but satisfies type checker
            return {"status": "retrying", "error": str(e), "file_path": file_path}
        else:
            # Max retries exceeded, return error result
            return {
                "file_path": file_path,
                "status": "failed",
                "error": str(e),
                "processed_at": datetime.now(UTC).isoformat(),
                "retries_attempted": self.request.retries,
            }


@celery_app.task(base=PhotoImportTask, bind=True)
def process_batch_photos(self, file_paths: list) -> dict[str, Any]:
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


@celery_app.task(base=PhotoImportTask, bind=True)
def scan_directory(directory_path: str, recursive: bool = True) -> dict[str, Any]:
    """Scan a directory for photo files using SecureDirectoryScanner."""
    try:
        from pathlib import Path

        from src.core.models.scan_result import ScanOptions, ScanStrategy
        from src.core.services.directory_scanner import SecureDirectoryScanner
        from src.core.services.file_system_service import SecurityConstraints

        # Convert string path to Path object
        path_obj = Path(directory_path)

        # Validate directory exists
        if not path_obj.exists() or not path_obj.is_dir():
            raise FileNotFoundError(
                f"Directory not found or not accessible: {directory_path}"
            )

        # Create security constraints for photo scanning
        constraints = SecurityConstraints(
            max_file_size_mb=500,  # Allow large photo files
            max_depth=10 if recursive else 1,
            follow_symlinks=False,
            skip_hidden_files=True,
            skip_hidden_directories=True,
        )

        # Initialize secure directory scanner

        assert (
            _photo_upload_service is not None
        ), "Photo upload service must be initialized"

        scanner = SecureDirectoryScanner(
            file_system_service=SecureFileSystemService.create_readonly_photo_service(
                allowed_directories=[path_obj]
            ),
            photo_processor=None,
            security_constraints=constraints,
        )

        # Configure scan options
        scan_options = ScanOptions(
            strategy=ScanStrategy.FULL_METADATA,
            recursive=recursive,
            max_files=None,  # No limit
            batch_size=100,  # Process in batches of 100
            include_metadata=True,
            include_thumbnails=False,
            skip_duplicates=True,
        )
        scan_result = scanner.scan_directory(path_obj, scan_options)

        # Extract photo file paths from scan results
        found_photos = [str(entry["path"]) for entry in scan_result.files]

        result = {
            "directory": directory_path,
            "recursive": recursive,
            "total_photos": len(found_photos),
            "photos": found_photos,
            "scanned_at": datetime.now(UTC).isoformat(),
            "status": "completed",
            "duration": scan_result.duration_seconds,
            # "scan_stats": { ## TODO: Add detailed scan stats when available
            #     "total_files_scanned": scan_result.total_files,
            #     "directories_scanned": scan_result.,
            #     "files_skipped": scan_result.,
            #     "security_violations": scan_result.,
            #     "scan_time_ms": scan_result.s,
            # },
        }

        logger.info(
            f"Directory scan completed: {directory_path} - "
            f"Found {len(found_photos)} photos in {scan_result.duration_seconds}ms"
        )
        return result

    except Exception as e:
        logger.error(f"Error scanning directory {directory_path}: {str(e)}")
        return {
            "directory": directory_path,
            "recursive": recursive,
            "status": "failed",
            "error": str(e),
            "scanned_at": datetime.now(UTC).isoformat(),
            "total_photos": 0,
            "photos": [],
        }


def generate_file_hash(file_path: str) -> str:
    """Generate SHA-256 hash of file for deduplication."""
    hash_sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)

    return hash_sha256.hexdigest()


@celery_app.task(base=PhotoImportTask, bind=True)
def generate_preview_task(
    self,
    photo_id: str,
    storage_path: str,
    filename: str,
    priority: str = "normal",
    requested_sizes: list = list(),
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


@celery_app.task(base=PhotoImportTask)
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
