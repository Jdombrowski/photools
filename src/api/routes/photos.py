import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.services.photo_upload_service import PhotoUploadService
from src.infrastructure.database import get_db_session

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize upload service
upload_service = PhotoUploadService()


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


@router.get("/photos")
async def list_photos(
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    processing_stage: str | None = None,
    camera_make: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    """List photos with pagination and optional search/filtering."""
    from sqlalchemy import and_, func, or_, select
    from sqlalchemy.orm import joinedload

    from src.infrastructure.database.models import Photo, PhotoMetadata

    # Build base query
    query = select(Photo).options(joinedload(Photo.photo_metadata))

    # Add filters
    filters = []
    if search:
        # Search in filename or camera make/model
        filters.append(
            or_(
                Photo.filename.ilike(f"%{search}%"),
                Photo.photo_metadata.has(
                    PhotoMetadata.camera_make.ilike(f"%{search}%")
                ),
                Photo.photo_metadata.has(
                    PhotoMetadata.camera_model.ilike(f"%{search}%")
                ),
            )
        )

    if processing_stage:
        filters.append(Photo.processing_stage == processing_stage)

    if camera_make:
        filters.append(
            Photo.photo_metadata.has(
                PhotoMetadata.camera_make.ilike(f"%{camera_make}%")
            )
        )

    if filters:
        query = query.where(and_(*filters))

    # Get total count
    count_query = select(func.count(Photo.id))
    if filters:
        count_query = count_query.where(and_(*filters))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(Photo.created_at.desc()).offset(offset).limit(limit)

    # Execute query
    result = await db.execute(query)
    photos = result.scalars().all()

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
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"Batch upload failed: {str(e)}")


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


@router.delete("/photos/{photo_id}")
async def delete_photo(photo_id: str, db: AsyncSession = Depends(get_db_session)):
    """Delete a photo by ID (TODO: Phase 2/3 - implement soft-delete with compaction)."""
    from src.core.services.preview_service import PreviewService

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
                priority=PreviewPriority.NORMAL,  # Use normal priority for bulk operations
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
        )


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
        )


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
        )


@router.post("/photos/scan-directory")
async def scan_directory(directory_path: str):
    """Scan a directory for photos to import."""
    if not os.path.exists(directory_path):
        raise HTTPException(
            status_code=400, detail=f"Directory does not exist: {directory_path}"
        )

    if not os.path.isdir(directory_path):
        raise HTTPException(
            status_code=400, detail=f"Path is not a directory: {directory_path}"
        )

    # For now, just return mock scan results
    return {
        "message": f"Directory scan initiated: {directory_path}",
        "status": "scanning",
        "estimated_files": "calculating...",
        "scan_id": f"scan_{datetime.utcnow().timestamp()}",
    }
