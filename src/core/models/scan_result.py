from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ScanStrategy(Enum):
    """Different scanning strategies for directory processing."""

    FAST_METADATA_ONLY = "fast_metadata_only"  # File info only, no photo processing
    FULL_METADATA = "full_metadata"  # Complete EXIF extraction
    INCREMENTAL = "incremental"  # Only scan changed files


class ScanStatus(Enum):
    """Status of a directory scan operation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScanProgress:
    """Progress tracking for directory scanning operations."""

    total_files: int = 0
    processed_files: int = 0
    successful_files: int = 0
    failed_files: int = 0
    current_file: Optional[str] = None
    start_time: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100

    @property
    def is_complete(self) -> bool:
        """Check if scanning is complete."""
        return self.processed_files >= self.total_files

    def add_error(self, error: str) -> None:
        """Add error to the error list."""
        self.errors.append(error)
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Scan error: {error}")


@dataclass
class ScanOptions:
    """Configuration options for directory scanning."""

    strategy: ScanStrategy = ScanStrategy.FULL_METADATA
    recursive: bool = True
    max_files: Optional[int] = None
    batch_size: int = 50
    include_metadata: bool = True
    include_thumbnails: bool = False
    skip_duplicates: bool = True
    progress_callback: Optional[Callable[["ScanProgress"], None]] = None


@dataclass
class ScanResult:
    """Result of a directory scanning operation."""

    # Basic scan information
    directory: str
    scan_id: str
    status: ScanStatus
    strategy: ScanStrategy

    # File counts
    total_files: int
    processed_files: int
    successful_files: int
    failed_files: int

    # Results and errors
    files: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    # Timing information
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Additional metadata
    scan_options: Optional[Dict[str, Any]] = None
    directory_stats: Optional[Dict[str, Any]] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate scan duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.processed_files == 0:
            return 0.0
        return (self.successful_files / self.processed_files) * 100

    @property
    def is_complete(self) -> bool:
        """Check if scan is complete (successful or failed)."""
        return self.status in [
            ScanStatus.COMPLETED,
            ScanStatus.FAILED,
            ScanStatus.CANCELLED,
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert scan result to dictionary for API responses."""
        return {
            "directory": self.directory,
            "scan_id": self.scan_id,
            "status": self.status.value,
            "strategy": self.strategy.value,
            "counts": {
                "total_files": self.total_files,
                "processed_files": self.processed_files,
                "successful_files": self.successful_files,
                "failed_files": self.failed_files,
            },
            "performance": {
                "success_rate_percent": round(self.success_rate, 2),
                "duration_seconds": self.duration_seconds,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
            },
            "files": self.files,
            "errors": self.errors,
            "scan_options": self.scan_options,
            "directory_stats": self.directory_stats,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary information without detailed file results."""
        result = self.to_dict()
        # Remove detailed file information for summary
        result.pop("files", None)
        if len(result.get("errors", [])) > 10:
            # Truncate error list for summary
            result["errors"] = result["errors"][:10] + ["... (truncated)"]
        return result


@dataclass
class BatchScanResult:
    """Result of scanning multiple directories."""

    directories: List[str]
    batch_id: str
    status: ScanStatus

    # Individual scan results
    scan_results: List[ScanResult] = field(default_factory=list)

    # Aggregate statistics
    total_directories: int = 0
    completed_directories: int = 0
    failed_directories: int = 0

    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def total_files_found(self) -> int:
        """Total files found across all directories."""
        return sum(result.total_files for result in self.scan_results)

    @property
    def total_files_processed(self) -> int:
        """Total files successfully processed across all directories."""
        return sum(result.successful_files for result in self.scan_results)

    @property
    def overall_success_rate(self) -> float:
        """Overall success rate across all directories."""
        total_processed = sum(result.processed_files for result in self.scan_results)
        total_successful = sum(result.successful_files for result in self.scan_results)

        if total_processed == 0:
            return 0.0
        return (total_successful / total_processed) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert batch scan result to dictionary."""
        return {
            "directories": self.directories,
            "batch_id": self.batch_id,
            "status": self.status.value,
            "counts": {
                "total_directories": self.total_directories,
                "completed_directories": self.completed_directories,
                "failed_directories": self.failed_directories,
                "total_files_found": self.total_files_found,
                "total_files_processed": self.total_files_processed,
            },
            "performance": {
                "overall_success_rate_percent": round(self.overall_success_rate, 2),
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
            },
            "scan_results": [result.get_summary() for result in self.scan_results],
        }
