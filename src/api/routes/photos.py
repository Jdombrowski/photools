import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from src.core.services.photo_upload_service import PhotoUploadService
from src.infrastructure.database import get_db_session

router = APIRouter()

# Initialize upload service
upload_service = PhotoUploadService()


# Pydantic models for request/response
class PhotoMetadata(BaseModel):
    filename: str
    file_size: int
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    created_date: Optional[datetime] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    iso: Optional[int] = None
    aperture: Optional[float] = None
    shutter_speed: Optional[str] = None
    focal_length: Optional[float] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None


class PhotoResponse(BaseModel):
    id: str
    metadata: PhotoMetadata
    processing_status: str
    created_at: datetime
    updated_at: datetime


@router.get("/photos")
async def list_photos(limit: int = 50, offset: int = 0, search: Optional[str] = None):
    """List photos with pagination and optional search"""
    # Mock response for now
    return {
        "photos": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
        "search": search,
    }


@router.post("/photos/upload")
async def upload_photo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session)
):
    """Upload a single photo for processing"""

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
            db
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/photos/batch-upload")
async def batch_upload_photos(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db_session)
):
    """Upload multiple photos for batch processing"""

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
            files_data.append((
                file_content, 
                file.filename, 
                file.content_type or "application/octet-stream"
            ))
        
        # Process batch upload
        result = await upload_service.process_batch_upload(files_data, db)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch upload failed: {str(e)}")


@router.get("/photos/{photo_id}")
async def get_photo(
    photo_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get photo details by ID"""
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
        "updated_at": photo.updated_at
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
async def delete_photo(
    photo_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a photo by ID"""
    success = await upload_service.delete_photo(photo_id, db)
    
    if not success:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    return {
        "message": f"Photo {photo_id} deleted successfully",
        "status": "deleted"
    }


@router.get("/photos/{photo_id}/file")
async def get_photo_file(
    photo_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Serve the actual photo file content"""
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
        media_type=photo.mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{photo.filename}"',
            "Content-Length": str(len(file_content))
        }
    )


@router.get("/storage/info")
async def get_storage_info():
    """Get storage backend information and statistics"""
    return upload_service.get_storage_info()


@router.post("/photos/scan-directory")
async def scan_directory(directory_path: str):
    """Scan a directory for photos to import"""

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
