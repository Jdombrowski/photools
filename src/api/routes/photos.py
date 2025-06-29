import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter()


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
async def upload_photo(file: UploadFile = File(...)):
    """Upload a single photo for processing"""

    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/tiff", "image/raw"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file.content_type} not supported. Allowed types: {allowed_types}",
        )

    # For now, just return mock response
    return {
        "message": "Photo uploaded successfully",
        "filename": file.filename,
        "content_type": file.content_type,
        "size": file.size if hasattr(file, "size") else "unknown",
        "status": "processing",
        "upload_id": f"mock_upload_{datetime.utcnow().timestamp()}",
    }


@router.post("/photos/batch-upload")
async def batch_upload_photos(files: List[UploadFile] = File(...)):
    """Upload multiple photos for batch processing"""

    if len(files) > 100:  # Reasonable limit
        raise HTTPException(
            status_code=400, detail="Too many files. Maximum 100 files per batch."
        )

    results = []
    for file in files:
        # Basic validation
        allowed_types = ["image/jpeg", "image/png", "image/tiff", "image/raw"]
        if file.content_type not in allowed_types:
            results.append(
                {
                    "filename": file.filename,
                    "status": "error",
                    "error": f"Unsupported file type: {file.content_type}",
                }
            )
            continue

        results.append(
            {
                "filename": file.filename,
                "status": "processing",
                "upload_id": f"batch_upload_{datetime.utcnow().timestamp()}_{file.filename}",
            }
        )

    return {
        "message": f"Batch upload initiated for {len(files)} files",
        "results": results,
    }


@router.get("/photos/{photo_id}")
async def get_photo(photo_id: str):
    """Get photo details by ID"""
    # Mock response
    return {
        "error": "Photo not found",
        "photo_id": photo_id,
        "message": "Database not yet implemented",
    }


@router.delete("/photos/{photo_id}")
async def delete_photo(photo_id: str):
    """Delete a photo by ID"""
    # Mock response
    return {
        "message": f"Photo {photo_id} would be deleted",
        "status": "pending_implementation",
    }


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

