import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from src.core.services.file_system_service import (
    AccessLevel,
    FileSystemEntry,
    FileSystemSecurityError,
    SecureFileSystemService,
)
from src.core.services.photo_processor_service import (
    PhotoMetadata,
    PhotoProcessingError,
    PhotoProcessorService,
)


class TestPhotoMetadata:
    """Test PhotoMetadata value object."""

    def test_photo_metadata_creation(self):
        """Test PhotoMetadata creation with all fields."""
        path = Path("/test/photo.jpg")
        date_taken = datetime(2023, 1, 15, 14, 30, 0)
        gps_coords = (40.7128, -74.0060)  # NYC coordinates

        metadata = PhotoMetadata(
            file_path=path,
            file_hash="abc123def456",
            file_size=1024000,
            mime_type="image/jpeg",
            dimensions=(1920, 1080),
            date_taken=date_taken,
            camera_make="Canon",
            camera_model="EOS R5",
            gps_coordinates=gps_coords,
            raw_exif={"ISO": 200, "FNumber": 2.8},
        )

        assert metadata.file_path == path
        assert metadata.file_hash == "abc123def456"
        assert metadata.file_size == 1024000
        assert metadata.mime_type == "image/jpeg"
        assert metadata.dimensions == (1920, 1080)
        assert metadata.date_taken == date_taken
        assert metadata.camera_make == "Canon"
        assert metadata.camera_model == "EOS R5"
        assert metadata.gps_coordinates == gps_coords
        assert metadata.raw_exif["ISO"] == 200

    def test_photo_metadata_minimal(self):
        """Test PhotoMetadata with minimal required fields."""
        path = Path("/test/simple.jpg")

        metadata = PhotoMetadata(
            file_path=path,
            file_hash="simple123",
            file_size=500000,
            mime_type="image/jpeg",
            dimensions=(800, 600),
        )

        assert metadata.file_path == path
        assert metadata.date_taken is None
        assert metadata.camera_make is None
        assert metadata.camera_model is None
        assert metadata.gps_coordinates is None
        assert metadata.raw_exif == {}

    def test_to_dict_conversion(self):
        """Test conversion to dictionary format."""
        path = Path("/test/photo.jpg")
        date_taken = datetime(2023, 1, 15, 14, 30, 0)
        gps_coords = (40.7128, -74.0060)

        metadata = PhotoMetadata(
            file_path=path,
            file_hash="abc123",
            file_size=1024,
            mime_type="image/jpeg",
            dimensions=(100, 200),
            date_taken=date_taken,
            camera_make="Test",
            camera_model="Model",
            gps_coordinates=gps_coords,
            raw_exif={"test": "value"},
        )

        result_dict = metadata.to_dict()

        assert result_dict["file_path"] == str(path)
        assert result_dict["file_hash"] == "abc123"
        assert result_dict["file_size"] == 1024
        assert result_dict["mime_type"] == "image/jpeg"
        assert result_dict["width"] == 100
        assert result_dict["height"] == 200
        assert result_dict["date_taken"] == date_taken.isoformat()
        assert result_dict["camera_make"] == "Test"
        assert result_dict["camera_model"] == "Model"
        assert result_dict["gps_lat"] == 40.7128
        assert result_dict["gps_lon"] == -74.0060
        assert result_dict["exif_data"] == {"test": "value"}

    def test_to_dict_with_nulls(self):
        """Test dictionary conversion with null values."""
        path = Path("/test/minimal.jpg")

        metadata = PhotoMetadata(
            file_path=path,
            file_hash="minimal123",
            file_size=500,
            mime_type="image/png",
            dimensions=(50, 75),
        )

        result_dict = metadata.to_dict()

        assert result_dict["date_taken"] is None
        assert result_dict["camera_make"] is None
        assert result_dict["camera_model"] is None
        assert result_dict["gps_lat"] is None
        assert result_dict["gps_lon"] is None
        assert result_dict["exif_data"] == {}


class TestPhotoProcessor:
    """Test PhotoProcessorService functionality."""

    @pytest.fixture
    def temp_directory(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_jpeg(self, temp_directory):
        """Create a valid JPEG file for testing."""
        # Create a simple RGB image
        img = Image.new("RGB", (100, 100), color="red")

        # Add some basic EXIF data

        jpeg_path = temp_directory / "test_photo.jpg"
        img.save(jpeg_path, "JPEG", quality=85)

        return jpeg_path

    @pytest.fixture
    def sample_png(self, temp_directory):
        """Create a PNG file for testing."""
        img = Image.new("RGB", (200, 150), color="blue")
        png_path = temp_directory / "test_photo.png"
        img.save(png_path, "PNG")
        return png_path

    @pytest.fixture
    def mock_file_system_service(self):
        """Create mock file system service."""
        service = MagicMock(spec=SecureFileSystemService)

        # Default to allowing access
        file_info = FileSystemEntry(
            path=Path("/test"),
            is_directory=False,
            size=1024,
            access_level=AccessLevel.READ_ONLY,
            permissions="rw-r--r--",
            last_modified=123456789.0,
            is_symlink=False,
        )
        service.get_file_info.return_value = file_info

        return service

    def test_processor_initialization_default(self):
        """Test processor initialization with defaults."""
        processor = PhotoProcessorService()

        assert processor.use_exiftool is False
        assert processor.file_system_service is None
        assert processor.max_file_size_bytes == 500 * 1024 * 1024  # 500MB

    def test_processor_initialization_with_file_system_service(
        self, mock_file_system_service
    ):
        """Test processor initialization with file system service."""
        processor = PhotoProcessorService(
            file_system_service=mock_file_system_service, max_file_size_mb=100
        )

        assert processor.file_system_service == mock_file_system_service
        assert processor.max_file_size_bytes == 100 * 1024 * 1024

    def test_is_supported_format(self):
        """Test file format support detection."""
        processor = PhotoProcessorService()

        # Supported formats
        assert processor.is_supported_format(Path("photo.jpg")) is True
        assert processor.is_supported_format(Path("photo.jpeg")) is True
        assert processor.is_supported_format(Path("photo.png")) is True
        assert processor.is_supported_format(Path("photo.tiff")) is True
        assert processor.is_supported_format(Path("photo.bmp")) is True
        assert processor.is_supported_format(Path("photo.webp")) is True

        # Case insensitive
        assert processor.is_supported_format(Path("PHOTO.JPG")) is True
        assert processor.is_supported_format(Path("Photo.Png")) is True

        # Unsupported formats
        assert processor.is_supported_format(Path("document.txt")) is False
        assert processor.is_supported_format(Path("video.mp4")) is False
        assert processor.is_supported_format(Path("audio.mp3")) is False

    def test_validate_file_access_with_file_system_service(
        self, mock_file_system_service
    ):
        """Test file access validation with file system service."""
        processor = PhotoProcessorService(file_system_service=mock_file_system_service)
        test_path = Path("/test/photo.jpg")

        # Should not raise exception for valid access
        processor.validate_file_access(test_path)
        mock_file_system_service.get_file_info.assert_called_once_with(test_path)

    def test_validate_file_access_denied(self, mock_file_system_service):
        """Test file access validation when access is denied."""
        # Configure mock to deny access
        file_info = FileSystemEntry(
            path=Path("/test"),
            is_directory=False,
            size=0,
            access_level=AccessLevel.NO_ACCESS,
            permissions="",
            last_modified=0,
            error="Permission denied",
        )
        mock_file_system_service.get_file_info.return_value = file_info

        processor = PhotoProcessorService(file_system_service=mock_file_system_service)

        with pytest.raises(PhotoProcessingError, match="File access denied"):
            processor.validate_file_access(Path("/test/photo.jpg"))

    def test_validate_file_access_security_error(self, mock_file_system_service):
        """Test file access validation with security error."""
        mock_file_system_service.get_file_info.side_effect = FileSystemSecurityError(
            "Security violation"
        )

        processor = PhotoProcessorService(file_system_service=mock_file_system_service)

        with pytest.raises(PhotoProcessingError, match="Security validation failed"):
            processor.validate_file_access(Path("/test/photo.jpg"))

    def test_validate_file_access_without_file_system_service(self, sample_jpeg):
        """Test file access validation without file system service."""
        processor = PhotoProcessorService()

        # Should not raise exception for existing file
        processor.validate_file_access(sample_jpeg)

    def test_validate_file_access_nonexistent_file(self):
        """Test validation of nonexistent file."""
        processor = PhotoProcessorService()
        nonexistent = Path("/nonexistent/photo.jpg")

        with pytest.raises(PhotoProcessingError, match="File not found"):
            processor.validate_file_access(nonexistent)

    def test_validate_file_access_large_file(self, temp_directory):
        """Test validation of file exceeding size limit."""
        # Create processor with small size limit
        processor = PhotoProcessorService(max_file_size_mb=1)  # 1MB limit

        # Create file larger than limit
        large_file = temp_directory / "large.jpg"
        large_file.write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB

        with pytest.raises(PhotoProcessingError, match="File too large"):
            processor.validate_file_access(large_file)

    def test_calculate_file_hash(self, sample_jpeg):
        """Test file hash calculation."""
        processor = PhotoProcessorService()

        hash1 = processor.calculate_file_hash(sample_jpeg)
        hash2 = processor.calculate_file_hash(sample_jpeg)

        # Same file should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length
        assert all(c in "0123456789abcdef" for c in hash1)

    def test_calculate_file_hash_different_files(self, sample_jpeg, sample_png):
        """Test that different files produce different hashes."""
        processor = PhotoProcessorService()

        hash_jpeg = processor.calculate_file_hash(sample_jpeg)
        hash_png = processor.calculate_file_hash(sample_png)

        assert hash_jpeg != hash_png

    def test_calculate_file_hash_permission_error(self, temp_directory):
        """Test hash calculation with permission error."""
        processor = PhotoProcessorService()

        # Create file and remove read permission
        test_file = temp_directory / "no_permission.jpg"
        test_file.write_bytes(b"test content")
        os.chmod(test_file, 0o000)

        try:
            with pytest.raises(
                PhotoProcessingError, match="Cannot read file for hashing"
            ):
                processor.calculate_file_hash(test_file)
        finally:
            # Restore permission for cleanup
            os.chmod(test_file, 0o644)

    def test_extract_exif_datetime(self):
        """Test EXIF datetime extraction."""
        processor = PhotoProcessorService()

        # Test with valid datetime
        exif_data = {"DateTimeOriginal": "2023:01:15 14:30:25"}
        result = processor.extract_exif_datetime(exif_data)

        expected = datetime(2023, 1, 15, 14, 30, 25)
        assert result == expected

    def test_extract_exif_datetime_multiple_tags(self):
        """Test EXIF datetime extraction with multiple datetime tags."""
        processor = PhotoProcessorService()

        # Test priority: DateTimeOriginal > DateTime > DateTimeDigitized
        exif_data = {
            "DateTime": "2023:01:15 10:00:00",
            "DateTimeOriginal": "2023:01:15 14:30:25",
            "DateTimeDigitized": "2023:01:15 16:00:00",
        }

        result = processor.extract_exif_datetime(exif_data)
        expected = datetime(2023, 1, 15, 14, 30, 25)  # Should use DateTimeOriginal
        assert result == expected

    def test_extract_exif_datetime_invalid_format(self):
        """Test EXIF datetime extraction with invalid format."""
        processor = PhotoProcessorService()

        exif_data = {"DateTime": "invalid_date_format"}
        result = processor.extract_exif_datetime(exif_data)

        assert result is None

    def test_extract_exif_datetime_missing(self):
        """Test EXIF datetime extraction when no datetime tags present."""
        processor = PhotoProcessorService()

        exif_data = {"ISO": 200, "FNumber": 2.8}
        result = processor.extract_exif_datetime(exif_data)

        assert result is None

    def test_extract_gps_coordinates(self):
        """Test GPS coordinate extraction from EXIF."""
        processor = PhotoProcessorService()

        # Mock GPS data (NYC coordinates)
        gps_info = {
            "GPSLatitude": (40, 42, 46.08),  # 40°42'46.08"N
            "GPSLatitudeRef": "N",
            "GPSLongitude": (74, 0, 21.6),  # 74°00'21.6"W
            "GPSLongitudeRef": "W",
        }
        exif_data = {"GPSInfo": gps_info}

        result = processor.extract_gps_coordinates(exif_data)

        # Convert expected coordinates
        expected_lat = 40 + 42 / 60 + 46.08 / 3600  # ~40.7128
        expected_lon = -(74 + 0 / 60 + 21.6 / 3600)  # ~-74.0060

        assert result is not None
        assert abs(result[0] - expected_lat) < 0.001
        assert abs(result[1] - expected_lon) < 0.001

    def test_extract_gps_coordinates_missing(self):
        """Test GPS coordinate extraction when GPS data missing."""
        processor = PhotoProcessorService()

        exif_data = {"ISO": 200}
        result = processor.extract_gps_coordinates(exif_data)

        assert result is None

    def test_extract_gps_coordinates_incomplete(self):
        """Test GPS coordinate extraction with incomplete data."""
        processor = PhotoProcessorService()

        # Missing longitude reference
        gps_info = {
            "GPSLatitude": (40, 42, 46.08),
            "GPSLatitudeRef": "N",
            "GPSLongitude": (74, 0, 21.6),
            # Missing GPSLongitudeRef
        }
        exif_data = {"GPSInfo": gps_info}

        result = processor.extract_gps_coordinates(exif_data)
        assert result is None

    def test_convert_gps_coordinate(self):
        """Test GPS coordinate conversion from DMS to decimal."""
        processor = PhotoProcessorService()

        # Test conversion: 40°42'46.08" = 40.7128°
        dms = (40, 42, 46.08)
        decimal = processor._convert_gps_coordinate(dms)

        expected = 40 + 42 / 60 + 46.08 / 3600
        assert abs(decimal - expected) < 0.0001

    def test_extract_metadata_pil(self, sample_jpeg):
        """Test metadata extraction using PIL."""
        processor = PhotoProcessorService()

        metadata = processor.extract_metadata_pil(sample_jpeg)

        assert isinstance(metadata, PhotoMetadata)
        assert metadata.file_path == sample_jpeg
        assert metadata.file_size > 0
        assert metadata.dimensions == (100, 100)  # From fixture
        assert metadata.mime_type == "image/jpeg"
        assert len(metadata.file_hash) == 64

    def test_extract_metadata_pil_png(self, sample_png):
        """Test metadata extraction from PNG file."""
        processor = PhotoProcessorService()

        metadata = processor.extract_metadata_pil(sample_png)

        assert metadata.file_path == sample_png
        assert metadata.dimensions == (200, 150)  # From fixture
        assert metadata.mime_type == "image/png"

    def test_extract_metadata_pil_invalid_image(self, temp_directory):
        """Test metadata extraction from invalid image file."""
        processor = PhotoProcessorService()

        # Create file with invalid image data
        invalid_image = temp_directory / "invalid.jpg"
        invalid_image.write_text("This is not an image")

        with pytest.raises(PhotoProcessingError, match="Cannot process image"):
            processor.extract_metadata_pil(invalid_image)

    def test_process_photo_success(self, sample_jpeg):
        """Test successful photo processing."""
        processor = PhotoProcessorService()

        metadata = processor.process_photo(sample_jpeg)

        assert isinstance(metadata, PhotoMetadata)
        assert metadata.file_path == sample_jpeg
        assert metadata.file_size > 0
        assert metadata.dimensions == (100, 100)

    def test_process_photo_with_file_system_service(
        self, sample_jpeg, mock_file_system_service
    ):
        """Test photo processing with file system service validation."""
        processor = PhotoProcessorService(file_system_service=mock_file_system_service)

        metadata = processor.process_photo(sample_jpeg)

        # Should call file system service for validation
        mock_file_system_service.get_file_info.assert_called_once()
        assert isinstance(metadata, PhotoMetadata)

    def test_process_photo_unsupported_format(self, temp_directory):
        """Test processing unsupported file format."""
        processor = PhotoProcessorService()

        txt_file = temp_directory / "document.txt"
        txt_file.write_text("This is a text file")

        with pytest.raises(PhotoProcessingError, match="Unsupported format"):
            processor.process_photo(txt_file)

    def test_process_photo_nonexistent_file(self):
        """Test processing nonexistent file."""
        processor = PhotoProcessorService()

        nonexistent = Path("/nonexistent/photo.jpg")

        with pytest.raises(PhotoProcessingError):
            processor.process_photo(nonexistent)

    def test_process_directory_deprecated_warning(self, temp_directory, sample_jpeg):
        """Test that process_directory issues deprecation warning."""
        processor = PhotoProcessorService()

        with pytest.warns() as warning_list:
            results = processor.process_directory(temp_directory, recursive=False)

        # Check that deprecation warning was issued
        deprecation_warnings = [
            w for w in warning_list if "deprecated" in str(w.message)
        ]
        assert len(deprecation_warnings) > 0

        # Should still work
        assert len(results) == 1
        assert results[0].file_path == sample_jpeg

    def test_process_directory_with_file_system_service(
        self, temp_directory, sample_jpeg, mock_file_system_service
    ):
        """Test directory processing with file system service."""
        processor = PhotoProcessorService(file_system_service=mock_file_system_service)

        results = processor.process_directory(temp_directory, recursive=False)

        # Should call file system service for validation
        mock_file_system_service.validate_path_access.assert_called()
        assert len(results) == 1

    def test_process_directory_access_denied(
        self, temp_directory, mock_file_system_service
    ):
        """Test directory processing when access is denied."""
        mock_file_system_service.validate_path_access.side_effect = (
            FileSystemSecurityError("Access denied")
        )

        processor = PhotoProcessorService(file_system_service=mock_file_system_service)

        with pytest.raises(PhotoProcessingError, match="Directory access denied"):
            processor.process_directory(temp_directory)

    def test_process_directory_mixed_files(
        self, temp_directory, sample_jpeg, sample_png
    ):
        """Test directory processing with mixed file types."""
        # Create non-image file
        txt_file = temp_directory / "readme.txt"
        txt_file.write_text("Documentation")

        processor = PhotoProcessorService()
        results = processor.process_directory(temp_directory, recursive=False)

        # Should only process image files
        assert len(results) == 2  # JPEG and PNG
        file_paths = [r.file_path for r in results]
        assert sample_jpeg in file_paths
        assert sample_png in file_paths
        assert txt_file not in file_paths

    def test_process_directory_with_errors(self, temp_directory, sample_jpeg):
        """Test directory processing with some files causing errors."""
        # Create invalid image file
        invalid_image = temp_directory / "invalid.jpg"
        invalid_image.write_text("Not an image")

        processor = PhotoProcessorService()
        results = processor.process_directory(temp_directory, recursive=False)

        # Should process valid image and skip invalid one
        assert len(results) == 1
        assert results[0].file_path == sample_jpeg

    def test_process_directory_recursive(self, temp_directory, sample_jpeg):
        """Test recursive directory processing."""
        # Create subdirectory with image
        subdir = temp_directory / "subdir"
        subdir.mkdir()

        # Copy sample image to subdirectory
        sub_image = subdir / "sub_photo.jpg"
        sub_image.write_bytes(sample_jpeg.read_bytes())

        processor = PhotoProcessorService()
        results = processor.process_directory(temp_directory, recursive=True)

        # Should find both images
        assert len(results) == 2
        file_paths = [r.file_path for r in results]
        assert sample_jpeg in file_paths
        assert sub_image in file_paths

    def test_process_directory_non_recursive(self, temp_directory, sample_jpeg):
        """Test non-recursive directory processing."""
        # Create subdirectory with image
        subdir = temp_directory / "subdir"
        subdir.mkdir()
        sub_image = subdir / "sub_photo.jpg"
        sub_image.write_bytes(sample_jpeg.read_bytes())

        processor = PhotoProcessorService()
        results = processor.process_directory(temp_directory, recursive=False)

        # Should only find image in root directory
        assert len(results) == 1
        assert results[0].file_path == sample_jpeg


class TestPhotoProcessingError:
    """Test PhotoProcessingError exception."""

    def test_photo_processing_error_creation(self):
        """Test creating PhotoProcessingError."""
        error = PhotoProcessingError("Test error message")
        assert str(error) == "Test error message"

    def test_photo_processing_error_inheritance(self):
        """Test that PhotoProcessingError inherits from Exception."""
        error = PhotoProcessingError("Test")
        assert isinstance(error, Exception)


@pytest.mark.integration
class TestPhotoProcessorIntegration:
    """Integration tests for PhotoProcessorService."""

    def test_real_image_processing(self):
        """Test processing a real image file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a real image with metadata
            img = Image.new("RGB", (300, 200), color="green")

            # Save as JPEG
            jpeg_path = temp_path / "test_real.jpg"
            img.save(jpeg_path, "JPEG", quality=90)

            processor = PhotoProcessorService()
            metadata = processor.process_photo(jpeg_path)

            assert metadata.file_path == jpeg_path
            assert metadata.dimensions == (300, 200)
            assert metadata.mime_type == "image/jpeg"
            assert metadata.file_size > 0
            assert len(metadata.file_hash) == 64

    def test_integration_with_file_system_service(self):
        """Test integration between PhotoProcessorService and SecureFileSystemService."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test image
            img = Image.new("RGB", (100, 100), color="red")
            jpeg_path = temp_path / "integration_test.jpg"
            img.save(jpeg_path, "JPEG")

            # Create file system service
            from src.core.services.file_system_service import SecurityConstraints

            constraints = SecurityConstraints(max_file_size_mb=1)
            file_system_service = SecureFileSystemService(
                allowed_directories=[temp_path], constraints=constraints
            )

            # Create processor with file system service
            processor = PhotoProcessorService(file_system_service=file_system_service)

            # Should successfully process
            metadata = processor.process_photo(jpeg_path)
            assert metadata.file_path == jpeg_path

            # Test with file outside allowed directory
            with tempfile.TemporaryDirectory() as outside_temp_dir:
                outside_image = Path(outside_temp_dir) / "outside.jpg"
                img.save(outside_image, "JPEG")

                with pytest.raises(PhotoProcessingError, match="File access denied"):
                    processor.process_photo(outside_image)
