import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from ...config.settings import (get_photo_directories, get_photo_extensions,
                                get_settings)
from ...core.models.scan_result import ScanStrategy
from ...core.services.directory_scanner import (ScanOptions,
                                                SecureDirectoryScanner)
from ...core.services.file_system_service import (FileSystemSecurityError,
                                                  SecureFileSystemService,
                                                  SecurityConstraints)
from ...core.services.photo_processor import PhotoProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/filesystem", tags=["filesystem"])


# Dependency injection
def get_file_system_service() -> SecureFileSystemService:
    """Get configured file system service with strict security constraints."""
    settings = get_settings()
    allowed_directories = get_photo_directories()

    # Use the most restrictive security settings for API access
    MAX_DIR_DEPTH = 5
    MAX_FILE_SIZE_MB = 100

    constraints = SecurityConstraints(
        max_file_size_mb=min(
            settings.photos.max_file_size_mb, MAX_FILE_SIZE_MB
        ),  # Cap at 100MB
        allowed_extensions=get_photo_extensions(),
        max_depth=min(
            settings.photos.max_directory_depth, MAX_DIR_DEPTH
        ),  # Cap at 5 levels deep
        follow_symlinks=False,  # Never follow symlinks in API
        skip_hidden_files=True,
        skip_hidden_directories=True,
        max_path_length=1024,  # Shorter path limit for API
        block_executable_extensions=settings.photos.block_executable_files,
        strict_extension_validation=True,
        enable_symlink_escape_detection=True,
        log_security_violations=settings.photos.log_security_violations,
    )

    service = SecureFileSystemService(
        allowed_directories=allowed_directories, constraints=constraints
    )

    # Log API security configuration
    logger.info(
        f"API FileSystem service configured with {len(allowed_directories)} allowed directories, max_size={constraints.max_file_size_mb}MB, max_depth={constraints.max_depth}"
    )

    return service


def get_directory_scanner(
    file_system_service: SecureFileSystemService = Depends(get_file_system_service),
) -> SecureDirectoryScanner:
    """Get configured directory scanner."""
    photo_processor = PhotoProcessor(file_system_service=file_system_service)
    return SecureDirectoryScanner(
        file_system_service=file_system_service, photo_processor=photo_processor
    )


@router.get("/directories", response_model=list[str])
async def list_allowed_directories() -> list[str]:
    """Get list of allowed photo directories.

    Returns:
        List of allowed directory paths

    """
    try:
        directories = get_photo_directories()
        return [str(d) for d in directories]
    except Exception as e:
        logger.error(f"Error getting allowed directories: {e}")
        raise HTTPException(status_code=500, detail="Failed to get allowed directories")


@router.get("/directories/{directory_path:path}/info")
async def get_directory_info(
    directory_path: str,
    file_system_service: SecureFileSystemService = Depends(get_file_system_service),
) -> dict[str, Any]:
    """Get information about a specific directory.

    Args:
        directory_path: Path to directory

    Returns:
        Directory information and statistics

    """
    try:
        path = Path(directory_path)

        # Validate directory access
        file_info = file_system_service.get_file_info(path)

        if not file_info.is_directory:
            raise HTTPException(status_code=400, detail="Path is not a directory")

        if file_info.error:
            raise HTTPException(
                status_code=403, detail=f"Access denied: {file_info.error}"
            )

        # Get directory statistics
        stats = file_system_service.get_directory_stats(path)

        return {
            "directory": str(path),
            "exists": path.exists(),
            "is_directory": file_info.is_directory,
            "access_level": file_info.access_level.value,
            "permissions": file_info.permissions,
            "last_modified": file_info.last_modified,
            "stats": stats,
        }

    except FileSystemSecurityError as e:
        logger.warning(f"Security error accessing directory {directory_path}: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting directory info for {directory_path}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get directory information"
        )


@router.get("/directories/{directory_path:path}/files")
async def list_directory_files(
    directory_path: str,
    recursive: bool = Query(default=True, description="Scan recursively"),
    max_depth: int | None = Query(
        default=None, description="Maximum depth for recursive scan"
    ),
    file_system_service: SecureFileSystemService = Depends(get_file_system_service),
) -> dict[str, Any]:
    """List files in a directory with security filtering.

    Args:
        directory_path: Path to directory
        recursive: Whether to scan recursively
        max_depth: Maximum recursion depth

    Returns:
        List of accessible files and directories

    """
    try:
        path = Path(directory_path)

        # List directory contents
        entries = file_system_service.list_directory(
            directory_path=path, recursive=recursive, max_depth=max_depth
        )

        # Separate files and directories
        files = []
        directories = []

        for entry in entries:
            entry_info = {
                "path": str(entry.path),
                "name": entry.path.name,
                "size": entry.size,
                "access_level": entry.access_level.value,
                "permissions": entry.permissions,
                "last_modified": entry.last_modified,
                "is_symlink": entry.is_symlink,
            }

            if entry.is_directory:
                directories.append(entry_info)
            else:
                entry_info["extension"] = entry.path.suffix.lower()
                files.append(entry_info)

        return {
            "directory": str(path),
            "total_entries": len(entries),
            "files": files,
            "directories": directories,
            "scan_options": {"recursive": recursive, "max_depth": max_depth},
        }

    except FileSystemSecurityError as e:
        logger.warning(f"Security error listing directory {directory_path}: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing directory {directory_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list directory contents")


@router.get("/directories/{directory_path:path}/photos")
async def list_photo_files(
    directory_path: str,
    recursive: bool = Query(default=True, description="Scan recursively"),
    file_system_service: SecureFileSystemService = Depends(get_file_system_service),
) -> dict[str, Any]:
    """List photo files in a directory.

    Args:
        directory_path: Path to directory
        recursive: Whether to scan recursively

    Returns:
        List of accessible photo files

    """
    try:
        path = Path(directory_path)

        # Get photo files
        photo_files = file_system_service.get_photo_files(
            directory_path=path, recursive=recursive
        )

        # Format response
        files = []
        total_size = 0
        extensions = {}

        for entry in photo_files:
            file_info = {
                "path": str(entry.path),
                "name": entry.path.name,
                "size": entry.size,
                "extension": entry.path.suffix.lower(),
                "last_modified": entry.last_modified,
                "access_level": entry.access_level.value,
            }
            files.append(file_info)

            total_size += entry.size
            ext = entry.path.suffix.lower()
            extensions[ext] = extensions.get(ext, 0) + 1

        return {
            "directory": str(path),
            "total_photos": len(files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "file_extensions": extensions,
            "files": files,
            "scan_options": {"recursive": recursive},
        }

    except FileSystemSecurityError as e:
        logger.warning(f"Security error listing photos in {directory_path}: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing photos in {directory_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list photo files")


@router.post("/scan/estimate")
async def estimate_scan(
    directory_path: str,
    recursive: bool = Query(default=True, description="Scan recursively"),
    directory_scanner: SecureDirectoryScanner = Depends(get_directory_scanner),
) -> dict[str, Any]:
    """Estimate the size and duration of a directory scan.

    Args:
        directory_path: Path to directory to scan
        recursive: Whether scan would be recursive

    Returns:
        Scan size estimates and timing information

    """
    try:
        path = Path(directory_path)
        estimate = directory_scanner.estimate_scan_size(path, recursive=recursive)
        return estimate

    except FileSystemSecurityError as e:
        logger.warning(f"Security error estimating scan for {directory_path}: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error estimating scan for {directory_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to estimate scan")


@router.post("/scan/start")
async def start_directory_scan(
    directory_path: str,
    background_tasks: BackgroundTasks,
    strategy: ScanStrategy = Query(
        default=ScanStrategy.FULL_METADATA, description="Scan strategy"
    ),
    recursive: bool = Query(default=True, description="Scan recursively"),
    max_files: int | None = Query(
        default=None, description="Maximum number of files to scan"
    ),
    batch_size: int = Query(default=50, description="Batch size for processing"),
    directory_scanner: SecureDirectoryScanner = Depends(get_directory_scanner),
) -> dict[str, Any]:
    """Start a directory scan operation.

    Args:
        directory_path: Path to directory to scan
        strategy: Scanning strategy (fast or full metadata)
        recursive: Whether to scan recursively
        max_files: Maximum number of files to scan
        batch_size: Batch size for processing

    Returns:
        Scan result information

    """
    try:
        path = Path(directory_path)

        # Create scan options
        options = ScanOptions(
            strategy=strategy,
            recursive=recursive,
            max_files=max_files,
            batch_size=batch_size,
            include_metadata=True,
        )

        # Start scan (synchronous for now, but returns quickly for fast scans)
        result = directory_scanner.scan_directory(path, options)

        return result.to_dict()

    except FileSystemSecurityError as e:
        logger.warning(f"Security error starting scan for {directory_path}: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        logger.warning(f"Invalid scan parameters for {directory_path}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting scan for {directory_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start directory scan")


@router.get("/scan/{scan_id}/status")
async def get_scan_status(
    scan_id: str,
    directory_scanner: SecureDirectoryScanner = Depends(get_directory_scanner),
) -> dict[str, Any]:
    """Get status of an active scan operation.

    Args:
        scan_id: ID of the scan to check

    Returns:
        Scan progress and status information

    """
    try:
        progress = directory_scanner.get_scan_progress(scan_id)

        if progress is None:
            raise HTTPException(status_code=404, detail="Scan not found")

        return {
            "scan_id": scan_id,
            "total_files": progress.total_files,
            "processed_files": progress.processed_files,
            "successful_files": progress.successful_files,
            "failed_files": progress.failed_files,
            "progress_percent": progress.progress_percent,
            "current_file": progress.current_file,
            "is_complete": progress.is_complete,
            "start_time": (
                progress.start_time.isoformat() if progress.start_time else None
            ),
            "estimated_completion": (
                progress.estimated_completion.isoformat()
                if progress.estimated_completion
                else None
            ),
            "errors": progress.errors[-10:],  # Last 10 errors
        }

    except Exception as e:
        logger.error(f"Error getting scan status for {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scan status")


@router.get("/scans/active")
async def list_active_scans(
    directory_scanner: SecureDirectoryScanner = Depends(get_directory_scanner),
) -> dict[str, Any]:
    """List all active scan operations.

    Returns:
        List of active scan IDs and basic information

    """
    try:
        active_scans = directory_scanner.list_active_scans()

        scan_info = []
        for scan_id in active_scans:
            progress = directory_scanner.get_scan_progress(scan_id)
            if progress:
                scan_info.append(
                    {
                        "scan_id": scan_id,
                        "progress_percent": progress.progress_percent,
                        "current_file": progress.current_file,
                        "is_complete": progress.is_complete,
                    }
                )

        return {"active_scans": len(active_scans), "scans": scan_info}

    except Exception as e:
        logger.error(f"Error listing active scans: {e}")
        raise HTTPException(status_code=500, detail="Failed to list active scans")


@router.delete("/scan/{scan_id}")
async def cancel_scan(
    scan_id: str,
    directory_scanner: SecureDirectoryScanner = Depends(get_directory_scanner),
) -> dict[str, Any]:
    """Cancel an active scan operation.

    Args:
        scan_id: ID of the scan to cancel

    Returns:
        Cancellation status

    """
    try:
        success = directory_scanner.cancel_scan(scan_id)

        if not success:
            raise HTTPException(
                status_code=404, detail="Scan not found or already completed"
            )

        return {
            "scan_id": scan_id,
            "cancelled": True,
            "message": "Scan cancelled successfully",
        }

    except Exception as e:
        logger.error(f"Error cancelling scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel scan")


@router.get("/config")
async def get_filesystem_config() -> dict[str, Any]:
    """Get current filesystem configuration and constraints.

    Returns:
        Current filesystem service configuration

    """
    try:
        settings = get_settings()

        return {
            "allowed_directories": [str(d) for d in get_photo_directories()],
            "photo_extensions": list(get_photo_extensions()),
            "security_constraints": {
                "max_file_size_mb": settings.photos.max_file_size_mb,
                "max_directory_depth": settings.photos.max_directory_depth,
                "follow_symlinks": settings.photos.follow_symlinks,
                "skip_hidden_files": settings.photos.skip_hidden_files,
                "skip_hidden_directories": settings.photos.skip_hidden_directories,
            },
            "scan_settings": {
                "enable_recursive_scan": settings.photos.enable_recursive_scan,
                "scan_batch_size": settings.photos.scan_batch_size,
            },
        }

    except Exception as e:
        logger.error(f"Error getting filesystem config: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get filesystem configuration"
        )
