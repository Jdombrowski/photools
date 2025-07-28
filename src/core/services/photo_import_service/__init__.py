"""PhotoImportService - Core service for importing photos from local filesystem.

This service orchestrates the complete photo import workflow:
1. Directory scanning with security validation
2. Photo filtering and duplicate detection
3. Metadata extraction and storage
4. Progress tracking and error handling
5. Import reporting and cleanup

Designed for offline-first photo management with comprehensive security.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from src.core.models.scan_result import ScanResult, ScanStrategy
from src.core.services.directory_scanner import SecureDirectoryScanner
from src.core.services.file_system_service import SecureFileSystemService
from src.core.services.photo_upload_service import PhotoUploadService
from src.core.storage.base import StorageBackend


class ImportStatus(Enum):
    """Status of an import operation."""

    PENDING = "pending"
    SCANNING = "scanning"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ImportPriority(Enum):
    """Priority level for import operations."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class ImportOptions:
    """Configuration options for photo import operations."""

    # Import behavior
    skip_duplicates: bool = True
    extract_metadata: bool = True
    generate_previews: bool = True
    organize_by_date: bool = True
    move_files: bool = False  # False = copy, True = move

    # Processing options
    batch_size: int = 50
    priority: ImportPriority = ImportPriority.NORMAL
    scan_strategy: ScanStrategy = ScanStrategy.FULL_METADATA

    # File filtering
    max_file_size_mb: int | None = None
    allowed_extensions: set[str] | None = None

    # Progress tracking
    progress_callback: Callable[["ImportProgress"], None] | None = None


@dataclass
class ImportProgress:
    """Progress tracking for import operations."""

    import_id: str
    status: ImportStatus

    # File counts
    total_files: int = 0
    scanned_files: int = 0
    imported_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0

    # Current operation
    current_file: str | None = None
    current_stage: str = "initializing"

    # Timing
    start_time: datetime | None = None
    end_time: datetime | None = None

    # Error tracking
    errors: list[str] = field(default_factory=list)

    @property
    def progress_percent(self) -> float:
        """Calculate overall progress percentage."""
        if self.total_files == 0:
            return 0.0
        processed = self.imported_files + self.skipped_files + self.failed_files
        return (processed / self.total_files) * 100

    @property
    def is_complete(self) -> bool:
        """Check if import is complete."""
        return self.status in [
            ImportStatus.COMPLETED,
            ImportStatus.FAILED,
            ImportStatus.CANCELLED,
        ]

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        processed = self.imported_files + self.skipped_files + self.failed_files
        if processed == 0:
            return 0.0
        return (self.imported_files / processed) * 100


@dataclass
class ImportResult:
    """Result of an import operation."""

    import_id: str
    source_directory: str
    status: ImportStatus

    # Summary counts
    total_files: int
    imported_files: int
    skipped_files: int
    failed_files: int

    # Timing
    start_time: datetime
    end_time: datetime

    # Details
    imported_photos: list[str] = field(default_factory=list)
    skipped_photos: list[str] = field(default_factory=list)
    error_details: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Calculate import duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_files == 0:
            return 0.0
        return (self.imported_files / self.total_files) * 100


class PhotoImportService:
    """Service for importing photos from local filesystem."""

    def __init__(
        self,
        directory_scanner: SecureDirectoryScanner,
        photo_upload_service: PhotoUploadService,
        storage_backend: StorageBackend,
    ):
        self.directory_scanner = directory_scanner
        self.photo_upload_service = photo_upload_service
        self.storage_backend = storage_backend
        self._active_imports: dict[str, ImportProgress] = {}

    async def import_directory(
        self,
        directory_path: Path,
        db_session,
        import_options: ImportOptions | None = None,
    ) -> ImportResult:
        """Import all photos from a directory.

        Args:
            directory_path: Path to directory to import
            import_options: Configuration options for import

        Returns:
            ImportResult with summary and details

        """
        options = import_options or ImportOptions()
        import_id = str(uuid.uuid4())

        # Initialize progress tracking
        progress = ImportProgress(
            import_id=import_id,
            status=ImportStatus.PENDING,
            start_time=datetime.now(),
            current_stage="initializing",
        )
        self._active_imports[import_id] = progress

        try:
            # Phase 1: Directory scanning
            progress.status = ImportStatus.SCANNING
            progress.current_stage = "scanning directory"
            self._update_progress(progress, options)

            scan_result = self._scan_directory(directory_path, options)
            progress.total_files = scan_result.total_files
            progress.scanned_files = scan_result.processed_files

            # Phase 2: Photo importing
            progress.status = ImportStatus.IMPORTING
            progress.current_stage = "importing photos"
            self._update_progress(progress, options)

            import_result = await self._import_photos(scan_result, options, progress, db_session)

            # Phase 3: Completion
            progress.status = ImportStatus.COMPLETED
            progress.current_stage = "completed"
            progress.end_time = datetime.now()
            self._update_progress(progress, options)

            return import_result

        except Exception as e:
            progress.status = ImportStatus.FAILED
            progress.current_stage = "failed"
            progress.end_time = datetime.now()
            progress.errors.append(str(e))
            self._update_progress(progress, options)

            # Return failed result
            return ImportResult(
                import_id=import_id,
                source_directory=str(directory_path),
                status=ImportStatus.FAILED,
                total_files=progress.total_files,
                imported_files=progress.imported_files,
                skipped_files=progress.skipped_files,
                failed_files=progress.failed_files,
                start_time=progress.start_time,
                end_time=progress.end_time,
                error_details=[{"error": str(e), "stage": "import"}],
            )
        finally:
            # Clean up tracking after delay
            # TODO: Implement cleanup timer
            pass

    async def import_single_photo(
        self,
        file_path: Path,
        db_session,
        import_options: ImportOptions | None = None,
    ) -> ImportResult:
        """Import a single photo file.

        Args:
            file_path: Path to photo file
            import_options: Configuration options for import

        Returns:
            ImportResult with import details

        """
        options = import_options or ImportOptions()
        import_id = str(uuid.uuid4())

        progress = ImportProgress(
            import_id=import_id,
            status=ImportStatus.IMPORTING,
            total_files=1,
            start_time=datetime.now(),
            current_file=str(file_path),
            current_stage="importing single photo",
        )
        self._active_imports[import_id] = progress

        try:
            # Import single photo
            self._update_progress(progress, options)

            # Check for duplicates if enabled
            if options.skip_duplicates:
                is_duplicate = await self._check_duplicate(file_path, db_session)
                if is_duplicate:
                    progress.skipped_files = 1
                    progress.status = ImportStatus.COMPLETED
                    progress.current_stage = "completed - duplicate skipped"
                    progress.end_time = datetime.now()
                    self._update_progress(progress, options)
                    
                    return ImportResult(
                        import_id=import_id,
                        source_directory=str(file_path.parent),
                        status=ImportStatus.COMPLETED,
                        total_files=1,
                        imported_files=0,
                        skipped_files=1,
                        failed_files=0,
                        start_time=progress.start_time,
                        end_time=progress.end_time,
                        skipped_photos=[str(file_path)],
                    )

            # Upload photo through existing service
            upload_result = await self._upload_photo_from_path(file_path, db_session)
            
            if upload_result.get("status") == "duplicate":
                # Storage-level duplicate detected
                progress.skipped_files = 1
                progress.status = ImportStatus.COMPLETED
                progress.current_stage = "completed - storage duplicate skipped"
                progress.end_time = datetime.now()
                self._update_progress(progress, options)
                
                return ImportResult(
                    import_id=import_id,
                    source_directory=str(file_path.parent),
                    status=ImportStatus.COMPLETED,
                    total_files=1,
                    imported_files=0,
                    skipped_files=1,
                    failed_files=0,
                    start_time=progress.start_time,
                    end_time=progress.end_time,
                    skipped_photos=[str(file_path)],
                )
            elif upload_result.get("status") != "success":
                # Upload failed
                progress.failed_files = 1
                progress.status = ImportStatus.FAILED
                progress.current_stage = "failed - upload error"
                progress.end_time = datetime.now()
                progress.errors.append(f"Upload failed: {upload_result.get('error', 'Unknown error')}")
                self._update_progress(progress, options)
                
                return ImportResult(
                    import_id=import_id,
                    source_directory=str(file_path.parent),
                    status=ImportStatus.FAILED,
                    total_files=1,
                    imported_files=0,
                    skipped_files=0,
                    failed_files=1,
                    start_time=progress.start_time,
                    end_time=progress.end_time,
                    error_details=[{"file": str(file_path), "error": upload_result.get("error", "Upload failed")}],
                )

            progress.imported_files = 1
            progress.status = ImportStatus.COMPLETED
            progress.current_stage = "completed"
            progress.end_time = datetime.now()
            self._update_progress(progress, options)

            return ImportResult(
                import_id=import_id,
                source_directory=str(file_path.parent),
                status=ImportStatus.COMPLETED,
                total_files=1,
                imported_files=1,
                skipped_files=0,
                failed_files=0,
                start_time=progress.start_time,
                end_time=progress.end_time,
                imported_photos=[str(file_path)],
            )

        except Exception as e:
            progress.failed_files = 1
            progress.status = ImportStatus.FAILED
            progress.current_stage = "failed"
            progress.end_time = datetime.now()
            progress.errors.append(str(e))
            self._update_progress(progress, options)

            return ImportResult(
                import_id=import_id,
                source_directory=str(file_path.parent),
                status=ImportStatus.FAILED,
                total_files=1,
                imported_files=0,
                skipped_files=0,
                failed_files=1,
                start_time=progress.start_time,
                end_time=progress.end_time,
                error_details=[{"file": str(file_path), "error": str(e)}],
            )
        finally:
            # Clean up tracking after delay
            # TODO: Implement cleanup timer
            pass

    def get_import_progress(self, import_id: str) -> ImportProgress | None:
        """Get progress information for an active import."""
        return self._active_imports.get(import_id)

    def list_active_imports(self) -> list[str]:
        """Get list of active import IDs."""
        return list(self._active_imports.keys())

    def cancel_import(self, import_id: str) -> bool:
        """Cancel an active import operation."""
        if import_id in self._active_imports:
            progress = self._active_imports[import_id]
            if not progress.is_complete:
                progress.status = ImportStatus.CANCELLED
                progress.current_stage = "cancelled"
                progress.end_time = datetime.now()
                return True
        return False

    def _scan_directory(
        self,
        directory_path: Path,
        options: ImportOptions,
    ) -> ScanResult:
        """Scan directory for photos using directory scanner."""
        from src.core.models.scan_result import ScanOptions

        scan_options = ScanOptions(
            strategy=options.scan_strategy,
            recursive=True,
            max_files=None,
            batch_size=options.batch_size,
            include_metadata=options.extract_metadata,
            skip_duplicates=options.skip_duplicates,
        )

        return self.directory_scanner.scan_directory(directory_path, scan_options)

    async def _import_photos(
        self,
        scan_result: ScanResult,
        options: ImportOptions,
        progress: ImportProgress,
        db_session,
    ) -> ImportResult:
        """Import photos from scan result."""
        imported_photos = []
        skipped_photos = []
        error_details = []

        for i, photo_info in enumerate(scan_result.files):
            try:
                progress.current_file = photo_info.get("file_path", "unknown")
                progress.current_stage = f"importing {i + 1}/{len(scan_result.files)}"
                self._update_progress(progress, options)

                file_path = Path(photo_info["file_path"])

                # Check for duplicates if enabled
                if options.skip_duplicates:
                    is_duplicate = await self._check_duplicate(file_path, db_session)
                    if is_duplicate:
                        skipped_photos.append(str(file_path))
                        progress.skipped_files += 1
                        continue

                # Upload photo
                upload_result = await self._upload_photo_from_path(file_path, db_session)
                
                if upload_result.get("status") == "success":
                    imported_photos.append(str(file_path))
                    progress.imported_files += 1
                elif upload_result.get("status") == "duplicate":
                    # Storage-level duplicate detected
                    skipped_photos.append(str(file_path))
                    progress.skipped_files += 1
                else:
                    # Upload failed
                    error_details.append(
                        {"file": str(file_path), "error": upload_result.get("error", "Upload failed")}
                    )
                    skipped_photos.append(str(file_path))
                    progress.failed_files += 1
                    progress.errors.append(
                        f"Failed to import {file_path}: {upload_result.get('error', 'Upload failed')}"
                    )

            except Exception as e:
                error_details.append(
                    {"file": photo_info.get("file_path", "unknown"), "error": str(e)}
                )
                skipped_photos.append(photo_info.get("file_path", "unknown"))
                progress.failed_files += 1
                progress.errors.append(
                    f"Failed to import {photo_info.get('file_path', 'unknown')}: {e}"
                )

        # Determine overall status based on results
        if progress.failed_files > 0 and progress.imported_files == 0:
            overall_status = ImportStatus.FAILED
        else:
            overall_status = ImportStatus.COMPLETED
            
        return ImportResult(
            import_id=progress.import_id,
            source_directory=scan_result.directory,
            status=overall_status,
            total_files=scan_result.total_files,
            imported_files=progress.imported_files,
            skipped_files=progress.skipped_files,
            failed_files=progress.failed_files,
            start_time=progress.start_time,
            end_time=datetime.now(),
            imported_photos=imported_photos,
            skipped_photos=skipped_photos,
            error_details=error_details,
        )

    async def _check_duplicate(self, file_path: Path, db_session) -> bool:
        """Check if a photo file is a duplicate based on file hash."""
        import hashlib
        from sqlalchemy import select
        from src.infrastructure.database.models import Photo
        
        # Calculate file hash
        file_content = file_path.read_bytes()
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        # Check if hash exists in database
        stmt = select(Photo).where(Photo.file_hash == file_hash)
        result = await db_session.execute(stmt)
        existing_photo = result.scalar_one_or_none()
        
        return existing_photo is not None

    async def _upload_photo_from_path(self, file_path: Path, db_session) -> dict:
        """Upload a photo file by reading it from disk and calling the upload service."""
        # Read file content
        file_content = file_path.read_bytes()
        
        # Determine content type based on file extension
        import mimetypes
        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = content_type or "application/octet-stream"
        
        # Call the upload service with file content
        return await self.photo_upload_service.process_upload(
            file_content=file_content,
            filename=file_path.name,
            content_type=content_type,
            db_session=db_session,
        )

    def _update_progress(self, progress: ImportProgress, options: ImportOptions):
        """Update progress and call callback if provided."""
        if options.progress_callback:
            options.progress_callback(progress)
