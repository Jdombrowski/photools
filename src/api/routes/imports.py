"""Import API endpoints for photo importing from local filesystem.

Provides REST endpoints for:
- Directory import operations
- Single file import operations
- Import progress tracking
- Import result retrieval
- Import cancellation

Designed for offline-first photo management workflow.
"""

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.scan_result import ScanStrategy
from src.infrastructure.database import get_db_session
from src.core.services.photo_import_service import (
    ImportOptions,
    ImportPriority,
    ImportStatus,
    PhotoImportService,
)
from src.core.services.service_factory import get_service_factory

router = APIRouter()


# Pydantic models for API requests/responses
class ImportDirectoryRequest(BaseModel):
    """Request model for directory import."""

    directory_path: str = Field(..., description="Path to directory to import")
    skip_duplicates: bool = Field(True, description="Skip duplicate photos")
    extract_metadata: bool = Field(True, description="Extract photo metadata")
    generate_previews: bool = Field(True, description="Generate preview images")
    organize_by_date: bool = Field(True, description="Organize by date taken")
    move_files: bool = Field(False, description="Move files instead of copy")
    batch_size: int = Field(50, ge=1, le=500, description="Batch size for processing")
    priority: ImportPriority = Field(
        ImportPriority.NORMAL, description="Import priority"
    )
    scan_strategy: ScanStrategy = Field(
        ScanStrategy.FULL_METADATA, description="Scanning strategy"
    )


class ImportFileRequest(BaseModel):
    """Request model for single file import."""

    file_path: str = Field(..., description="Path to photo file to import")
    extract_metadata: bool = Field(True, description="Extract photo metadata")
    generate_previews: bool = Field(True, description="Generate preview images")
    organize_by_date: bool = Field(True, description="Organize by date taken")
    move_files: bool = Field(False, description="Move file instead of copy")


class ImportProgressResponse(BaseModel):
    """Response model for import progress."""

    import_id: str
    status: ImportStatus
    total_files: int
    scanned_files: int
    imported_files: int
    skipped_files: int
    failed_files: int
    current_file: str | None = None
    current_stage: str
    start_time: str | None = None
    end_time: str | None = None
    progress_percent: float
    success_rate: float
    errors: list[str]


class ImportResultResponse(BaseModel):
    """Response model for import results."""

    import_id: str
    source_directory: str
    status: ImportStatus
    total_files: int
    imported_files: int
    skipped_files: int
    failed_files: int
    start_time: str
    end_time: str
    duration_seconds: float
    success_rate: float
    imported_photos: list[str]
    skipped_photos: list[str]
    error_details: list[dict]


class ImportStatusResponse(BaseModel):
    """Response model for import status."""

    import_id: str
    status: ImportStatus
    message: str


# Dependency injection
def get_import_service() -> PhotoImportService:
    """Get configured PhotoImportService instance using service factory."""
    service_factory = get_service_factory()
    return service_factory.get_photo_import_service()


# API Endpoints
@router.post("/directory", response_model=ImportStatusResponse)
async def import_directory(
    request: ImportDirectoryRequest,
    background_tasks: BackgroundTasks,
    import_service: PhotoImportService = Depends(get_import_service),
    db: AsyncSession = Depends(get_db_session),
):
    """Start importing all photos from a directory.

    This endpoint initiates a background import operation for all photos
    in the specified directory. Returns immediately with an import ID
    that can be used to track progress.

    Args:
        request: Directory import configuration
        background_tasks: FastAPI background tasks
        import_service: Import service dependency

    Returns:
        Import status with ID for tracking

    """
    try:
        directory_path = Path(request.directory_path)

        # Validate directory exists and is accessible
        if not directory_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Directory not found: {directory_path}"
            )

        if not directory_path.is_dir():
            raise HTTPException(
                status_code=400, detail=f"Path is not a directory: {directory_path}"
            )

        # Create import options
        import_options = ImportOptions(
            skip_duplicates=request.skip_duplicates,
            extract_metadata=request.extract_metadata,
            generate_previews=request.generate_previews,
            organize_by_date=request.organize_by_date,
            move_files=request.move_files,
            batch_size=request.batch_size,
            priority=request.priority,
            scan_strategy=request.scan_strategy,
        )

        # Start import as background task
        import_result = await import_service.import_directory(
            directory_path=directory_path, db_session=db, import_options=import_options
        )

        return ImportStatusResponse(
            import_id=import_result.import_id,
            status=import_result.status,
            message=f"Import started for directory: {directory_path}",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start directory import: {str(e)}"
        ) from e


@router.post("/file", response_model=ImportResultResponse)
async def import_file(
    request: ImportFileRequest,
    import_service: PhotoImportService = Depends(get_import_service),
    db: AsyncSession = Depends(get_db_session),
):
    """Import a single photo file.

    Imports a single photo file with metadata extraction and storage.
    This is a synchronous operation that returns the full result.

    Args:
        request: File import configuration
        import_service: Import service dependency

    Returns:
        Complete import result

    """
    try:
        file_path = Path(request.file_path)

        # Validate file exists and is accessible
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

        if not file_path.is_file():
            raise HTTPException(
                status_code=400, detail=f"Path is not a file: {file_path}"
            )

        # Create import options
        import_options = ImportOptions(
            extract_metadata=request.extract_metadata,
            generate_previews=request.generate_previews,
            organize_by_date=request.organize_by_date,
            move_files=request.move_files,
        )

        # Import file
        import_result = await import_service.import_single_photo(
            file_path=file_path, db_session=db, import_options=import_options
        )

        return ImportResultResponse(
            import_id=import_result.import_id,
            source_directory=import_result.source_directory,
            status=import_result.status,
            total_files=import_result.total_files,
            imported_files=import_result.imported_files,
            skipped_files=import_result.skipped_files,
            failed_files=import_result.failed_files,
            start_time=import_result.start_time.isoformat(),
            end_time=import_result.end_time.isoformat(),
            duration_seconds=import_result.duration_seconds,
            success_rate=import_result.success_rate,
            imported_photos=import_result.imported_photos,
            skipped_photos=import_result.skipped_photos,
            error_details=import_result.error_details,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to import file: {str(e)}"
        ) from e


@router.get("/{import_id}/progress", response_model=ImportProgressResponse)
async def get_import_progress(
    import_id: str, import_service: PhotoImportService = Depends(get_import_service)
):
    """Get progress information for an active import.

    Returns real-time progress information for the specified import operation.

    Args:
        import_id: Import operation identifier
        import_service: Import service dependency

    Returns:
        Import progress information

    """
    progress = import_service.get_import_progress(import_id)

    if not progress:
        raise HTTPException(status_code=404, detail=f"Import not found: {import_id}")

    return ImportProgressResponse(
        import_id=progress.import_id,
        status=progress.status,
        total_files=progress.total_files,
        scanned_files=progress.scanned_files,
        imported_files=progress.imported_files,
        skipped_files=progress.skipped_files,
        failed_files=progress.failed_files,
        current_file=progress.current_file,
        current_stage=progress.current_stage,
        start_time=progress.start_time.isoformat() if progress.start_time else None,
        end_time=progress.end_time.isoformat() if progress.end_time else None,
        progress_percent=progress.progress_percent,
        success_rate=progress.success_rate,
        errors=progress.errors,
    )


@router.get("/{import_id}/result", response_model=ImportResultResponse)
async def get_import_result(
    import_id: str, import_service: PhotoImportService = Depends(get_import_service)
):
    """Get final result for a completed import.

    Returns the complete result information for a finished import operation.

    Args:
        import_id: Import operation identifier
        import_service: Import service dependency

    Returns:
        Complete import result

    """
    progress = import_service.get_import_progress(import_id)

    if not progress:
        raise HTTPException(status_code=404, detail=f"Import not found: {import_id}")

    if not progress.is_complete:
        raise HTTPException(
            status_code=400, detail=f"Import not yet complete: {import_id}"
        )

    # TODO: Implement proper result storage and retrieval
    # For now, construct from progress information
    return ImportResultResponse(
        import_id=progress.import_id,
        source_directory="",  # TODO: Store source directory
        status=progress.status,
        total_files=progress.total_files,
        imported_files=progress.imported_files,
        skipped_files=progress.skipped_files,
        failed_files=progress.failed_files,
        start_time=progress.start_time.isoformat() if progress.start_time else "",
        end_time=progress.end_time.isoformat() if progress.end_time else "",
        duration_seconds=0.0,  # TODO: Calculate duration
        success_rate=progress.success_rate,
        imported_photos=[],  # TODO: Store imported photos list
        skipped_photos=[],  # TODO: Store skipped photos list
        error_details=[],  # TODO: Store error details
    )


@router.post("/{import_id}/cancel", response_model=ImportStatusResponse)
async def cancel_import(
    import_id: str, import_service: PhotoImportService = Depends(get_import_service)
):
    """Cancel an active import operation.

    Attempts to cancel the specified import operation. The import may not
    stop immediately if it's in the middle of processing a file.

    Args:
        import_id: Import operation identifier
        import_service: Import service dependency

    Returns:
        Import status after cancellation

    """
    success = import_service.cancel_import(import_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Import not found or cannot be cancelled: {import_id}",
        )

    return ImportStatusResponse(
        import_id=import_id,
        status=ImportStatus.CANCELLED,
        message=f"Import cancelled: {import_id}",
    )


@router.get("/active", response_model=list[str])
async def list_active_imports(
    import_service: PhotoImportService = Depends(get_import_service),
):
    """List all active import operations.

    Returns a list of import IDs for all currently active import operations.

    Args:
        import_service: Import service dependency

    Returns:
        List of active import IDs

    """
    return import_service.list_active_imports()
