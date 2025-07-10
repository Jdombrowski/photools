import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ...models.scan_result import (
    ScanOptions,
    ScanProgress,
    ScanResult,
    ScanStatus,
    ScanStrategy,
)
from ..file_system_service import SecureFileSystemService, SecurityConstraints
from ..photo_processor import PhotoProcessingError, PhotoProcessor

logger = logging.getLogger(__name__)


class SecureDirectoryScanner:
    """Secure directory scanner with readonly access and comprehensive metadata extraction.

    Features:
    - Security-first design with path validation
    - Progress tracking and callbacks
    - Configurable scanning strategies
    - Batch processing for performance
    - Error handling and recovery
    - Integration with existing PhotoProcessor
    """

    def __init__(
        self,
        file_system_service: SecureFileSystemService,
        photo_processor: PhotoProcessor | None = None,
        security_constraints: SecurityConstraints | None = None,
    ):
        """Initialize secure directory scanner.

        Args:
            file_system_service: Secure file system service instance
            photo_processor: Photo processor for metadata extraction
            security_constraints: Additional security constraints

        """
        self.file_system_service = file_system_service
        self.photo_processor = photo_processor or PhotoProcessor()
        self.security_constraints = security_constraints or SecurityConstraints()

        # Track active scans
        self._active_scans: dict[str, ScanProgress] = {}

        logger.info("SecureDirectoryScanner initialized")

    def validate_scan_request(self, directory_path: Path, options: ScanOptions) -> None:
        """Validate scan request for security and feasibility.

        Args:
            directory_path: Directory to scan
            options: Scan options

        Raises:
            ValueError: If scan request is invalid
            FileSystemSecurityError: If security validation fails

        """
        # Security validation through file system service
        self.file_system_service.validate_path_access(directory_path)

        # Check if directory exists and is accessible
        if not directory_path.exists():
            raise ValueError(f"Directory does not exist: {directory_path}")

        if not directory_path.is_dir():
            raise ValueError(f"Path is not a directory: {directory_path}")

        # Validate scan options
        if options.max_files is not None and options.max_files <= 0:
            raise ValueError("max_files must be positive")

        if options.batch_size <= 0:
            raise ValueError("batch_size must be positive")

        logger.debug(f"Scan request validated for {directory_path}")

    def estimate_scan_size(
        self, directory_path: Path, recursive: bool = True
    ) -> dict[str, Any]:
        """Estimate the size and scope of a directory scan.

        Args:
            directory_path: Directory to analyze
            recursive: Whether to scan recursively

        Returns:
            Dictionary with scan size estimates

        """
        try:
            photo_files = self.file_system_service.get_photo_files(
                directory_path, recursive=recursive
            )

            total_size = sum(entry.size for entry in photo_files)

            # Estimate processing time (rough calculation)
            estimated_seconds_per_file = 0.5  # Conservative estimate
            estimated_duration_seconds = len(photo_files) * estimated_seconds_per_file

            return {
                "directory": str(directory_path),
                "total_photo_files": len(photo_files),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "estimated_duration_seconds": estimated_duration_seconds,
                "estimated_duration_minutes": round(estimated_duration_seconds / 60, 1),
                "recursive": recursive,
                "largest_file_size": max((e.size for e in photo_files), default=0),
                "file_extensions": list({e.path.suffix.lower() for e in photo_files}),
            }

        except Exception as e:
            logger.error(f"Error estimating scan size for {directory_path}: {e}")
            return {"directory": str(directory_path), "error": str(e)}

    def scan_directory_fast(
        self, directory_path: Path, options: ScanOptions
    ) -> ScanResult:
        """Fast directory scan - file system metadata only.

        Args:
            directory_path: Directory to scan
            options: Scan options

        Returns:
            ScanResult with file system information

        """
        scan_id = f"fast_scan_{datetime.now().isoformat()}"
        progress = ScanProgress(start_time=datetime.now())

        try:
            self.validate_scan_request(directory_path, options)
            self._active_scans[scan_id] = progress

            # Get photo files with security filtering
            photo_files = self.file_system_service.get_photo_files(
                directory_path, recursive=options.recursive
            )

            # Apply max_files limit if specified
            if options.max_files:
                photo_files = photo_files[: options.max_files]

            progress.total_files = len(photo_files)

            # Process files in batches
            results = []
            for i, entry in enumerate(photo_files):
                progress.current_file = str(entry.path)
                progress.processed_files = i + 1

                if options.progress_callback:
                    options.progress_callback(progress)

                # Create simplified result for fast scan
                file_result = {
                    "file_path": str(entry.path),
                    "file_size": entry.size,
                    "last_modified": entry.last_modified,
                    "access_level": entry.access_level.value,
                    "is_symlink": entry.is_symlink,
                    "scan_strategy": options.strategy.value,
                }

                results.append(file_result)
                progress.successful_files += 1

            # Clean up active scan tracking
            del self._active_scans[scan_id]

            return ScanResult(
                directory=str(directory_path),
                scan_id=scan_id,
                status=ScanStatus.COMPLETED,
                strategy=options.strategy,
                total_files=len(results),
                processed_files=len(results),
                successful_files=progress.successful_files,
                failed_files=progress.failed_files,
                files=results,
                errors=progress.errors,
                start_time=progress.start_time,
                end_time=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Fast scan failed for {directory_path}: {e}")
            return ScanResult(
                directory=str(directory_path),
                scan_id=scan_id,
                status=ScanStatus.FAILED,
                strategy=options.strategy,
                total_files=0,
                processed_files=0,
                successful_files=0,
                failed_files=1,
                files=[],
                errors=[str(e)],
                start_time=progress.start_time,
                end_time=datetime.now(),
            )

    def scan_directory_full(
        self, directory_path: Path, options: ScanOptions
    ) -> ScanResult:
        """Full directory scan with complete metadata extraction.

        Args:
            directory_path: Directory to scan
            options: Scan options

        Returns:
            ScanResult with complete photo metadata

        """
        scan_id = f"full_scan_{datetime.now().isoformat()}"
        progress = ScanProgress(start_time=datetime.now())

        try:
            self.validate_scan_request(directory_path, options)
            self._active_scans[scan_id] = progress

            # Get photo files
            photo_files = self.file_system_service.get_photo_files(
                directory_path, recursive=options.recursive
            )

            if options.max_files:
                photo_files = photo_files[: options.max_files]

            progress.total_files = len(photo_files)

            # Process files with full metadata extraction
            results = []
            for i, entry in enumerate(photo_files):
                progress.current_file = str(entry.path)
                progress.processed_files = i + 1

                if options.progress_callback:
                    options.progress_callback(progress)

                try:
                    # Extract full metadata using PhotoProcessor
                    metadata = self.photo_processor.process_photo(entry.path)

                    file_result = {
                        "file_path": str(entry.path),
                        "metadata": metadata.to_dict(),
                        "file_system_info": {
                            "access_level": entry.access_level.value,
                            "permissions": entry.permissions,
                            "is_symlink": entry.is_symlink,
                        },
                        "scan_strategy": options.strategy.value,
                    }

                    results.append(file_result)
                    progress.successful_files += 1

                except PhotoProcessingError as e:
                    progress.add_error(f"Failed to process {entry.path}: {e}")
                    progress.failed_files += 1
                    continue
                except Exception as e:
                    progress.add_error(f"Unexpected error processing {entry.path}: {e}")
                    progress.failed_files += 1
                    continue

            # Clean up
            del self._active_scans[scan_id]

            return ScanResult(
                directory=str(directory_path),
                scan_id=scan_id,
                status=ScanStatus.COMPLETED,
                strategy=options.strategy,
                total_files=len(photo_files),
                processed_files=progress.processed_files,
                successful_files=progress.successful_files,
                failed_files=progress.failed_files,
                files=results,
                errors=progress.errors,
                start_time=progress.start_time,
                end_time=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Full scan failed for {directory_path}: {e}")
            return ScanResult(
                directory=str(directory_path),
                scan_id=scan_id,
                status=ScanStatus.FAILED,
                strategy=options.strategy,
                total_files=0,
                processed_files=0,
                successful_files=0,
                failed_files=1,
                files=[],
                errors=[str(e)],
                start_time=datetime.now(),
                end_time=datetime.now(),
            )

    def scan_directory(
        self, directory_path: Path, options: ScanOptions | None = None
    ) -> ScanResult:
        """Main entry point for directory scanning.

        Args:
            directory_path: Directory to scan
            options: Scan options (uses defaults if not provided)

        Returns:
            ScanResult based on the chosen strategy

        """
        options = options or ScanOptions()

        logger.info(f"Starting {options.strategy.value} scan of {directory_path}")

        if options.strategy == ScanStrategy.FAST_METADATA_ONLY:
            return self.scan_directory_fast(directory_path, options)
        elif options.strategy == ScanStrategy.FULL_METADATA:
            return self.scan_directory_full(directory_path, options)
        elif options.strategy == ScanStrategy.INCREMENTAL:
            # TODO: Implement incremental scanning
            logger.warning(
                "Incremental scanning not yet implemented, falling back to full scan"
            )
            options.strategy = ScanStrategy.FULL_METADATA
            return self.scan_directory_full(directory_path, options)
        else:
            raise ValueError(f"Unknown scan strategy: {options.strategy}")

    def get_scan_progress(self, scan_id: str) -> ScanProgress | None:
        """Get progress information for an active scan."""
        return self._active_scans.get(scan_id)

    def list_active_scans(self) -> list[str]:
        """Get list of active scan IDs."""
        return list(self._active_scans.keys())

    def cancel_scan(self, scan_id: str) -> bool:
        """Cancel an active scan.

        Args:
            scan_id: ID of scan to cancel

        Returns:
            True if scan was cancelled, False if not found

        """
        if scan_id in self._active_scans:
            del self._active_scans[scan_id]
            logger.info(f"Cancelled scan {scan_id}")
            return True
        return False
