import hashlib
import logging
import mimetypes
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

from ..file_system_service import (
    AccessLevel,
    FileSystemSecurityError,
    SecureFileSystemService,
)

logger = logging.getLogger(__name__)


class PhotoMetadata:
    """Value object for photo metadata - makes testing and validation easier."""

    def __init__(
        self,
        file_path: Path,
        file_hash: str,
        file_size: int,
        mime_type: str,
        dimensions: tuple[int, int],
        date_taken: datetime | None = None,
        camera_make: str | None = None,
        camera_model: str | None = None,
        gps_coordinates: tuple[float, float] | None = None,
        raw_exif: dict[str, Any] | None = None,
    ):
        self.file_path = file_path
        self.file_hash = file_hash
        self.file_size = file_size
        self.mime_type = mime_type
        self.dimensions = dimensions
        self.date_taken = date_taken
        self.camera_make = camera_make
        self.camera_model = camera_model
        self.gps_coordinates = gps_coordinates
        self.raw_exif = raw_exif or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses and database storage."""
        return {
            "file_path": str(self.file_path),
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "width": self.dimensions[0],
            "height": self.dimensions[1],
            "date_taken": self.date_taken.isoformat() if self.date_taken else None,
            "camera_make": self.camera_make,
            "camera_model": self.camera_model,
            "gps_lat": self.gps_coordinates[0] if self.gps_coordinates else None,
            "gps_lon": self.gps_coordinates[1] if self.gps_coordinates else None,
            "exif_data": self.raw_exif,
        }


class PhotoProcessorService:
    """Core photo processing service with security-first design.

    Design principles:
    - Single responsibility: just extract metadata
    - Security-first with file access validation
    - Fail fast with clear error messages
    - Incremental complexity (start simple, add ExifTool later)
    - Easy to test and mock
    """

    SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}

    def __init__(
        self,
        use_exiftool: bool = False,
        file_system_service: SecureFileSystemService | None = None,
        max_file_size_mb: int = 500,
    ):
        self.use_exiftool = use_exiftool
        self.file_system_service = file_system_service
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

        if use_exiftool:
            # TODO: Add ExifTool integration for advanced metadata
            logger.warning(
                "ExifTool integration not yet implemented, falling back to PIL"
            )
            self.use_exiftool = False

    def validate_file_access(self, file_path: Path) -> None:
        """Validate that file can be safely accessed for processing.

        Args:
            file_path: Path to validate

        Raises:
            PhotoProcessingError: If file access is not allowed

        """
        # Use file system service for validation if available
        if self.file_system_service:
            try:
                file_info = self.file_system_service.get_file_info(file_path)

                if file_info.access_level == AccessLevel.NO_ACCESS:
                    raise PhotoProcessingError(
                        f"File access denied: {file_path}. Reason: {file_info.error or 'Security constraints'}"
                    )

                if file_info.error:
                    raise PhotoProcessingError(f"File access error: {file_info.error}")

            except FileSystemSecurityError as e:
                raise PhotoProcessingError(f"Security validation failed: {e}") from e
        else:
            # Basic validation without file system service
            if not file_path.exists():
                raise PhotoProcessingError(f"File not found: {file_path}")

            if not os.access(file_path, os.R_OK):
                raise PhotoProcessingError(
                    f"No read permission for file: {file_path}"
                ) from None

            # Check file size
            try:
                file_size = file_path.stat().st_size
                if file_size > self.max_file_size_bytes:
                    raise PhotoProcessingError(
                        f"File too large: {file_size} bytes (max: {self.max_file_size_bytes})"
                    )
            except OSError as e:
                raise PhotoProcessingError(f"Cannot access file stats: {e}") from e

    def is_supported_format(self, file_path: Path) -> bool:
        """Check if file format is supported."""
        return file_path.suffix.lower() in self.SUPPORTED_FORMATS

    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash for duplicate detection.

        Args:
            file_path: Path to file

        Returns:
            SHA-256 hash as hexadecimal string

        Raises:
            PhotoProcessingError: If file cannot be read

        """
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                # Read in chunks to handle large files efficiently
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except (OSError, PermissionError) as e:
            raise PhotoProcessingError(f"Cannot read file for hashing: {e}") from e

    def extract_exif_datetime(self, exif_data: dict[str, Any]) -> datetime | None:
        """Extract and parse datetime from EXIF data."""
        # Try multiple EXIF datetime fields in priority order
        datetime_tags = ["DateTimeOriginal", "DateTime", "DateTimeDigitized"]

        for tag in datetime_tags:
            if tag in exif_data and exif_data[tag]:
                try:
                    # EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
                    return datetime.strptime(exif_data[tag], "%Y:%m:%d %H:%M:%S")
                except ValueError as e:
                    logger.warning(f"Failed to parse datetime {exif_data[tag]}: {e}")
                    continue

        return None

    def extract_gps_coordinates(
        self, exif_data: dict[str, Any]
    ) -> tuple[float, float] | None:
        """Extract GPS coordinates from EXIF data."""
        if "GPSInfo" not in exif_data:
            return None

        gps_info = exif_data["GPSInfo"]

        try:
            # Extract latitude
            if "GPSLatitude" in gps_info and "GPSLatitudeRef" in gps_info:
                lat = self._convert_gps_coordinate(gps_info["GPSLatitude"])
                if gps_info["GPSLatitudeRef"] == "S":
                    lat = -lat
            else:
                return None

            # Extract longitude
            if "GPSLongitude" in gps_info and "GPSLongitudeRef" in gps_info:
                lon = self._convert_gps_coordinate(gps_info["GPSLongitude"])
                if gps_info["GPSLongitudeRef"] == "W":
                    lon = -lon
            else:
                return None

            return (lat, lon)

        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Failed to extract GPS coordinates: {e}")
            return None

    def _convert_gps_coordinate(self, coord_tuple) -> float:
        """Convert GPS coordinate from DMS (degrees, minutes, seconds) to decimal."""
        degrees, minutes, seconds = coord_tuple
        return float(degrees) + float(minutes) / 60 + float(seconds) / 3600

    def extract_metadata_pil(self, file_path: Path) -> PhotoMetadata:
        """Extract metadata using PIL - fallback method."""
        # Basic file information
        file_size = file_path.stat().st_size
        mime_type, _ = mimetypes.guess_type(str(file_path))
        file_hash = self.calculate_file_hash(file_path)

        try:
            with Image.open(file_path) as img:
                dimensions = img.size

                # Extract EXIF data
                raw_exif = {}
                exif_dict = img.getexif()

                if exif_dict:
                    # Convert numeric EXIF tags to readable names
                    for tag_id, value in exif_dict.items():
                        tag_name = TAGS.get(tag_id, tag_id)
                        raw_exif[tag_name] = value

                    # Handle GPS info separately
                    if "GPSInfo" in raw_exif:
                        gps_dict = {}
                        for gps_tag_id, gps_value in raw_exif["GPSInfo"].items():
                            gps_tag_name = GPSTAGS.get(gps_tag_id, gps_tag_id)
                            gps_dict[gps_tag_name] = gps_value
                        raw_exif["GPSInfo"] = gps_dict

                # Extract structured metadata
                date_taken = self.extract_exif_datetime(raw_exif)
                gps_coordinates = self.extract_gps_coordinates(raw_exif)

                return PhotoMetadata(
                    file_path=file_path,
                    file_hash=file_hash,
                    file_size=file_size,
                    mime_type=mime_type or "application/octet-stream",
                    dimensions=dimensions,
                    date_taken=date_taken,
                    camera_make=raw_exif.get("Make"),
                    camera_model=raw_exif.get("Model"),
                    gps_coordinates=gps_coordinates,
                    raw_exif=raw_exif,
                )

        except Exception as e:
            logger.error(f"Failed to process image {file_path}: {e}")
            raise PhotoProcessingError(f"Cannot process image {file_path}: {e}") from e

    def process_photo(self, file_path: Path) -> PhotoMetadata:
        """Main entry point for photo processing with security validation.

        Args:
            file_path: Path to photo file

        Returns:
            PhotoMetadata object with extracted information

        Raises:
            PhotoProcessingError: If processing fails or security validation fails

        """
        logger.debug(f"Starting photo processing: {file_path}")

        # Security validation first
        self.validate_file_access(file_path)

        # Format validation
        if not self.is_supported_format(file_path):
            raise PhotoProcessingError(
                f"Unsupported format: {file_path.suffix}. "
                f"Supported: {', '.join(self.SUPPORTED_FORMATS)}"
            )

        logger.info(f"Processing photo: {file_path}")

        try:
            # For now, always use PIL. Later we'll add ExifTool option
            result = self.extract_metadata_pil(file_path)
            logger.debug(f"Successfully processed photo: {file_path}")
            return result
        except Exception as e:
            logger.error(f"Failed to process photo {file_path}: {e}")
            raise

    async def process_photo_async(self, file_path: str) -> dict[str, Any]:
        """Async wrapper for photo processing that returns a dict result.

        This method avoids using run_in_executor to prevent SQLAlchemy greenlet issues.
        Since the underlying PIL/metadata operations are CPU-bound but don't require
        database access, we can run them synchronously in the async context.

        Args:
            file_path: Path to photo file as string

        Returns:
            Dict with success status and metadata

        """
        try:
            file_path_obj = Path(file_path)
            # Run synchronously in the current async context to avoid greenlet issues
            metadata = self.process_photo(file_path_obj)
            return {"success": True, "metadata": metadata.to_dict()}
        except PhotoProcessingError as e:
            logger.error(f"Photo processing failed: {e}")
            return {"success": False, "error": str(e), "metadata": None}
        except Exception as e:
            logger.error(f"Unexpected error in photo processing: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "metadata": None,
            }

    def process_directory(
        self, directory_path: Path, recursive: bool = True
    ) -> list[PhotoMetadata]:
        """Process all supported images in a directory with security validation.

        Args:
            directory_path: Directory to process
            recursive: Whether to process recursively

        Returns:
            List of PhotoMetadata objects for successfully processed files

        Note:
            This method is deprecated in favor of using SecureDirectoryScanner
            for better security, progress tracking, and error handling.

        """
        import warnings

        warnings.warn(
            "PhotoProcessorService.process_directory is deprecated. "
            "Use SecureDirectoryScanner for better security and features.",
            DeprecationWarning,
            stacklevel=2,
        )

        # Basic security validation
        if self.file_system_service:
            try:
                self.file_system_service.validate_path_access(directory_path)
            except FileSystemSecurityError as e:
                raise PhotoProcessingError(f"Directory access denied: {e}") from e
        else:
            # Basic validation without file system service
            if not directory_path.exists() or not directory_path.is_dir():
                raise PhotoProcessingError(
                    f"Directory not found or not a directory: {directory_path}"
                )

        results = []
        pattern = "**/*" if recursive else "*"

        try:
            for file_path in directory_path.glob(pattern):
                if file_path.is_file() and self.is_supported_format(file_path):
                    try:
                        metadata = self.process_photo(file_path)
                        results.append(metadata)
                        logger.debug(f"Successfully processed: {file_path}")
                    except PhotoProcessingError as e:
                        logger.error(f"Failed to process {file_path}: {e}")
                        continue
        except (OSError, PermissionError) as e:
            raise PhotoProcessingError(
                f"Error accessing directory {directory_path}: {e}"
            ) from e

        logger.info(f"Processed {len(results)} photos from {directory_path}")
        return results


class PhotoProcessingError(Exception):
    """Custom exception for photo processing errors."""

    pass


# Quick validation function for development
def validate_processor():
    """Quick smoke test for development."""
    processor = PhotoProcessorService()

    # Test with a sample image (you'll need to create this)
    sample_path = Path("test_photo.jpg")
    if sample_path.exists():
        try:
            metadata = processor.process_photo(sample_path)
            print(f"✅ Successfully processed: {metadata.file_path}")
            print(f"   Dimensions: {metadata.dimensions}")
            print(f"   Hash: {metadata.file_hash[:8]}...")
            return True
        except PhotoProcessingError as e:
            print(f"❌ Processing failed: {e}")
            return False
    else:
        print("⚠️  No test image found - create test_photo.jpg to validate")
        return None


if __name__ == "__main__":
    validate_processor()
