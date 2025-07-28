import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.services.photo_query_builder import build_photo_query
from src.core.services.photo_upload_service import PhotoUploadService
from src.core.services.preview_service import PreviewService
from src.infrastructure.database import get_db_session

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize upload service
upload_service = PhotoUploadService()

# Constants
MAX_PHOTOS_PER_REQUEST = 200  # Hard limit for safety


# Pydantic models for request/response
class PhotoMetadata(BaseModel):
    filename: str
    file_size: int
    mime_type: str
    width: int | None = None
    height: int | None = None
    created_date: datetime | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    iso: int | None = None
    aperture: float | None = None
    shutter_speed: str | None = None
    focal_length: float | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None


class PhotoResponse(BaseModel):
    id: str
    metadata: PhotoMetadata
    processing_status: str
    created_at: datetime
    updated_at: datetime


class WorkflowStage:
    """Workflow-based rating system mapping."""

    REJECT = 0  # Delete/Reject - Doesn't meet basic standards
    REVIEW_NEEDED = 1  # Review Needed - Uncertain, needs second look
    ARCHIVE = 2  # Archive - Decent but not worth editing time
    EDIT_QUEUE = 3  # Edit Queue - Meets goals, ready for enhancement
    PORTFOLIO = 4  # Portfolio - Finished, exceptional work
    SHOWCASE = 5  # Showcase - Exceptional, competition/exhibition worthy

    STAGE_DESCRIPTIONS = {
        0: "Reject/Delete - Doesn't meet basic standards",
        1: "Review Needed - Uncertain, needs second look",
        2: "Archive - Decent but not worth editing time",
        3: "Edit Queue - Meets goals, ready for enhancement",
        4: "Portfolio - Finished, exceptional work",
        5: "Showcase - Exceptional, competition/exhibition worthy",
    }

    STAGE_NAMES = {
        0: "Reject",
        1: "Review",
        2: "Archive",
        3: "Edit Queue",
        4: "Portfolio",
        5: "Showcase",
    }

    @classmethod
    def is_valid(cls, rating: int) -> bool:
        """Check if rating is valid workflow stage."""
        return rating in cls.STAGE_DESCRIPTIONS

    @classmethod
    def get_description(cls, rating: int) -> str:
        """Get description for workflow stage."""
        return cls.STAGE_DESCRIPTIONS.get(rating, "Unknown stage")

    @classmethod
    def get_name(cls, rating: int) -> str:
        """Get short name for workflow stage."""
        return cls.STAGE_NAMES.get(rating, "Unknown")


class PhotoRatingRequest(BaseModel):
    rating: int  # Workflow stage (0-5)


@router.get("/photos")
async def list_photos(
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    processing_stage: str | None = None,
    camera_make: str | None = None,
    rating: int | None = None,
    rating_min: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    aperture_min: float | None = None,
    aperture_max: float | None = None,
    iso_min: int | None = None,
    iso_max: int | None = None,
    has_gps: bool | None = None,
    show_all: bool = False,
    debug: bool = False,
    db: AsyncSession = Depends(get_db_session),
):
    """List photos with pagination and optional search/filtering.

    By default, only shows recent photos (last 30 days) unless specific filters are applied
    or show_all=true is used.
    """
    try:
        # Build query using the query builder pattern
        query_builder = (
            build_photo_query(db)
            .debug_mode(debug)
            .with_search(search)
            .with_processing_stage(processing_stage)
            .with_camera_make(camera_make)
            .with_rating(rating, rating_min)
            .with_date_range(date_from, date_to)
            .with_camera_settings(aperture_min, aperture_max, iso_min, iso_max)
            .with_gps(has_gps)
            .with_whitelist_defaults(show_all)
            .with_pagination(limit, offset, MAX_PHOTOS_PER_REQUEST)
        )

        # Execute query
        photos = await query_builder.execute()

        # Get total count (simplified for now - could be optimized)
        total = len(photos) + offset if photos else 0

        if debug:
            logger.info(
                f"Query executed with filters: {query_builder.get_applied_filters()}"
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Format response
    photos_data = []
    for photo in photos:
        photo_data = {
            "id": photo.id,
            "filename": photo.filename,
            "file_size": photo.file_size,
            "mime_type": photo.mime_type,
            "width": photo.width,
            "height": photo.height,
            "processing_status": photo.processing_status,
            "processing_stage": photo.processing_stage,
            "priority_level": photo.priority_level,
            "needs_attention": photo.needs_attention,
            "created_at": photo.created_at,
            "updated_at": photo.updated_at,
        }

        # Add metadata if available
        if photo.photo_metadata:
            photo_data["metadata"] = {
                "camera_make": photo.photo_metadata.camera_make,
                "camera_model": photo.photo_metadata.camera_model,
                "lens_model": photo.photo_metadata.lens_model,
                "date_taken": photo.photo_metadata.date_taken,
                "gps_latitude": photo.photo_metadata.gps_latitude,
                "gps_longitude": photo.photo_metadata.gps_longitude,
                "focal_length": photo.photo_metadata.focal_length,
                "aperture": photo.photo_metadata.aperture,
                "iso": photo.photo_metadata.iso,
            }

        photos_data.append(photo_data)

    return {
        "photos": photos_data,
        "total": total,
        "limit": limit,
        "offset": offset,
        "search": search,
        "processing_stage": processing_stage,
        "camera_make": camera_make,
        "has_more": offset + limit < total,
    }


@router.post("/photos/upload")
async def upload_photo(
    file: UploadFile = File(...), db: AsyncSession = Depends(get_db_session)
):
    """Upload a single photo for processing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    try:
        # Read file content
        file_content = await file.read()

        # Process upload using our service
        result = await upload_service.process_upload(
            file_content,
            file.filename,
            file.content_type or "application/octet-stream",
            db,
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}") from e


@router.post("/photos/batch-upload")
async def batch_upload_photos(
    files: list[UploadFile] = File(...), db: AsyncSession = Depends(get_db_session)
):
    """Upload multiple photos for batch processing."""
    if len(files) > 100:  # Reasonable limit
        raise HTTPException(
            status_code=400, detail="Too many files. Maximum 100 files per batch."
        )

    try:
        # Prepare file data
        files_data = []
        for file in files:
            if not file.filename:
                continue

            file_content = await file.read()
            files_data.append(
                (
                    file_content,
                    file.filename,
                    file.content_type or "application/octet-stream",
                )
            )

        # Process batch upload
        result = await upload_service.process_batch_upload(files_data, db)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Batch upload failed: {str(e)}"
        ) from e


@router.get("/photos/{photo_id}")
async def get_photo(photo_id: str, db: AsyncSession = Depends(get_db_session)):
    """Get photo details by ID."""
    from sqlalchemy import select

    from src.infrastructure.database.models import Photo, PhotoMetadata

    # Get photo record
    stmt = select(Photo).where(Photo.id == photo_id)
    result = await db.execute(stmt)
    photo = result.scalar_one_or_none()

    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Get metadata if available
    metadata_stmt = select(PhotoMetadata).where(PhotoMetadata.photo_id == photo_id)
    metadata_result = await db.execute(metadata_stmt)
    metadata = metadata_result.scalar_one_or_none()

    response = {
        "id": photo.id,
        "filename": photo.filename,
        "file_size": photo.file_size,
        "mime_type": photo.mime_type,
        "width": photo.width,
        "height": photo.height,
        "file_hash": photo.file_hash,
        "processing_status": photo.processing_status,
        "processing_stage": photo.processing_stage,
        "priority_level": photo.priority_level,
        "needs_attention": photo.needs_attention,
        "created_at": photo.created_at,
        "updated_at": photo.updated_at,
    }

    if metadata:
        response["metadata"] = {
            "camera_make": metadata.camera_make,
            "camera_model": metadata.camera_model,
            "lens_model": metadata.lens_model,
            "focal_length": metadata.focal_length,
            "aperture": metadata.aperture,
            "shutter_speed": metadata.shutter_speed,
            "iso": metadata.iso,
            "date_taken": metadata.date_taken,
            "gps_latitude": metadata.gps_latitude,
            "gps_longitude": metadata.gps_longitude,
        }

    return response


@router.put("/photos/{photo_id}/rating")
async def set_photo_rating(
    photo_id: str,
    rating_request: PhotoRatingRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Set or update a photo's workflow stage rating (0-5)."""
    from sqlalchemy import select, update

    from src.infrastructure.database.models import Photo

    # Validate rating using workflow stage system
    if not WorkflowStage.is_valid(rating_request.rating):
        raise HTTPException(
            status_code=400,
            detail=f"Rating must be between 0-5. Available stages: {list(WorkflowStage.STAGE_NAMES.values())}",
        )

    # Check if photo exists
    stmt = select(Photo).where(Photo.id == photo_id)
    result = await db.execute(stmt)
    photo = result.scalar_one_or_none()

    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Update rating with workflow stage
    update_stmt = (
        update(Photo)
        .where(Photo.id == photo_id)
        .values(
            user_rating=rating_request.rating,
            rating_updated_at=datetime.now(UTC),
        )
    )

    await db.execute(update_stmt)
    await db.commit()

    return {
        "photo_id": photo_id,
        "rating": rating_request.rating,
        "workflow_stage": WorkflowStage.get_name(rating_request.rating),
        "description": WorkflowStage.get_description(rating_request.rating),
        "updated_at": datetime.now(UTC),
    }


@router.get("/photos/workflow-stages")
async def get_workflow_stages():
    """Get available workflow stage ratings and their descriptions."""
    return {
        "stages": [
            {
                "value": stage,
                "name": WorkflowStage.get_name(stage),
                "description": WorkflowStage.get_description(stage),
            }
            for stage in sorted(WorkflowStage.STAGE_DESCRIPTIONS.keys())
        ]
    }


@router.delete("/photos/{photo_id}")
async def delete_photo(photo_id: str, db: AsyncSession = Depends(get_db_session)):
    """Delete a photo by ID.

    TODO: Phase 2/3 - implement soft-delete with compaction.
    """
    preview_service = PreviewService(db)

    # Delete previews first
    await preview_service.delete_photo_previews(photo_id)

    # Delete photo and storage
    success = await upload_service.delete_photo(photo_id, db)

    if not success:
        raise HTTPException(status_code=404, detail="Photo not found")

    return {"message": f"Photo {photo_id} deleted successfully", "status": "deleted"}


@router.get("/photos/{photo_id}/file")
async def get_photo_file(photo_id: str, db: AsyncSession = Depends(get_db_session)):
    """Serve the actual photo file content."""
    from fastapi import Response
    from sqlalchemy import select

    from src.infrastructure.database.models import Photo

    # Get photo record to check mime type and filename
    stmt = select(Photo).where(Photo.id == photo_id)
    result = await db.execute(stmt)
    photo = result.scalar_one_or_none()

    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Get file content from storage
    file_content = await upload_service.get_photo_content(photo_id, db)

    if not file_content:
        raise HTTPException(status_code=404, detail="Photo file not found in storage")

    return Response(
        content=file_content,
        media_type=getattr(photo, "mime_type", None),
        headers={
            "Content-Disposition": f'inline; filename="{photo.filename}"',
            "Content-Length": str(len(file_content)),
        },
    )


@router.get("/photos/{photo_id}/preview")
async def get_photo_preview(
    photo_id: str,
    size: str = "medium",
    format: str = "jpg",
    db: AsyncSession = Depends(get_db_session),
):
    """Get a preview/thumbnail of the photo."""
    from src.core.services.preview_service import PreviewService

    preview_service = PreviewService(db)
    return await preview_service.get_or_generate_preview(
        photo_id=photo_id,
        size=size,
        format=format,
        is_user_request=True,  # This is a direct user request
    )


@router.get("/photos/{photo_id}/preview/info")
async def get_photo_preview_info(
    photo_id: str, db: AsyncSession = Depends(get_db_session)
):
    """Get information about available previews for a photo."""
    from src.core.services.preview_service import PreviewService

    preview_service = PreviewService(db)
    # This will validate photo exists and return preview info
    await preview_service._get_photo_or_404(photo_id)  # Validate photo exists
    preview_info = preview_service.get_preview_info(photo_id)

    return {"photo_id": photo_id, "previews": preview_info}


@router.post("/photos/{photo_id}/preview/generate")
async def generate_photo_previews(
    photo_id: str, db: AsyncSession = Depends(get_db_session)
):
    """Generate all preview sizes for a photo."""
    from src.core.services.preview_service import PreviewService

    preview_service = PreviewService(db)
    return await preview_service.generate_all_previews_for_photo(photo_id)


@router.get("/storage/info")
async def get_storage_info():
    """Get storage backend information and statistics."""
    return upload_service.get_storage_info()


@router.get("/storage/preview-stats")
async def get_preview_storage_stats(db: AsyncSession = Depends(get_db_session)):
    """Get preview storage statistics."""
    from src.core.services.preview_service import PreviewService

    preview_service = PreviewService(db)
    return preview_service.get_storage_stats()


@router.post("/admin/bulk-generate-previews")
async def trigger_bulk_preview_generation(
    batch_size: int = 10,
    db: AsyncSession = Depends(get_db_session),
):
    """Trigger background bulk preview generation with smart queueing."""
    from sqlalchemy import select

    from src.core.services.preview_queue_service import PreviewPriority, preview_queue
    from src.infrastructure.database.models import Photo

    try:
        # Get photos that need preview generation
        stmt = select(Photo).limit(batch_size)
        result = await db.execute(stmt)
        photos = result.scalars().all()

        if not photos:
            return {"message": "No photos found to process", "processed": 0}
        ""
        queued_count = 0
        results = []

        for photo in photos:
            queue_result = preview_queue.queue_preview_generation(
                photo_id=str(photo.id),
                storage_path=str(photo.file_path),
                filename=str(photo.filename),
                # Use normal priority for bulk operations
                priority=PreviewPriority.NORMAL,
            )

            if queue_result["status"] in ["queued", "existing"]:
                queued_count += 1

            results.append(
                {
                    "photo_id": photo.id,
                    "filename": photo.filename,
                    "status": queue_result["status"],
                    "task_id": queue_result.get("task_id"),
                }
            )

        return {
            "message": f"Bulk preview generation initiated for {queued_count} photos",
            "total_photos": len(photos),
            "queued": queued_count,
            "results": results[:5],  # Show first 5 results
            "has_more": len(results) > 5,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start bulk preview generation: {str(e)}"
        ) from e


@router.get("/admin/queue-stats")
async def get_queue_statistics():
    """Get current preview generation queue statistics."""
    from src.core.services.preview_queue_service import preview_queue

    try:
        stats = preview_queue.get_queue_stats()

        # Cleanup completed tasks
        cleaned_count = preview_queue.cleanup_completed_tasks()
        if cleaned_count > 0:
            stats["cleaned_completed_tasks"] = cleaned_count

        return stats

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get queue statistics: {str(e)}"
        ) from e


@router.get("/admin/task-status/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a background task."""
    from src.workers.celery_app import celery_app

    try:
        task_result = celery_app.AsyncResult(task_id)

        return {
            "task_id": task_id,
            "status": task_result.status,
            "result": task_result.result if task_result.ready() else None,
            "successful": task_result.successful() if task_result.ready() else None,
            "failed": task_result.failed() if task_result.ready() else None,
            "info": task_result.info if task_result.state == "PROGRESS" else None,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get task status: {str(e)}"
        ) from e


@router.post("/photos/scan-directory")
async def scan_directory(directory_path: str):
    """Scan a directory for photos to import."""
    from pathlib import Path

    from src.core.models.scan_result import ScanOptions, ScanStrategy
    from src.core.services.service_factory import get_service_factory

    path = Path(directory_path)

    if not path.exists():
        raise HTTPException(
            status_code=400, detail=f"Directory does not exist: {directory_path}"
        )

    if not path.is_dir():
        raise HTTPException(
            status_code=400, detail=f"Path is not a directory: {directory_path}"
        )

    try:
        # Get directory scanner from service factory
        service_factory = get_service_factory()
        directory_scanner = service_factory.get_directory_scanner()

        # First do a fast scan to get estimate
        scan_options = ScanOptions(
            strategy=ScanStrategy.FAST_METADATA_ONLY,
            recursive=True,
            max_files=None,
            batch_size=50,
        )

        # Perform the scan
        scan_result = directory_scanner.scan_directory(path, scan_options)

        return {
            "scan_id": scan_result.scan_id,
            "directory": scan_result.directory,
            "status": scan_result.status.value,
            "strategy": scan_result.strategy.value,
            "total_files": scan_result.total_files,
            "processed_files": scan_result.processed_files,
            "successful_files": scan_result.successful_files,
            "failed_files": scan_result.failed_files,
            "start_time": (
                scan_result.start_time.isoformat() if scan_result.start_time else None
            ),
            "end_time": (
                scan_result.end_time.isoformat() if scan_result.end_time else None
            ),
            "files": scan_result.files[:10],  # Return first 10 files as preview
            "errors": scan_result.errors,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Directory scan failed: {str(e)}"
        ) from e
