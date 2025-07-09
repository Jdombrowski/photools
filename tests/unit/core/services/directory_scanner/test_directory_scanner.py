import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.models.scan_result import (ScanOptions, ScanProgress, ScanResult,
                                         ScanStatus, ScanStrategy)
from src.core.services.directory_scanner import SecureDirectoryScanner
from src.core.services.file_system_service import (AccessLevel,
                                                   FileSystemEntry,
                                                   SecureFileSystemService,
                                                   SecurityConstraints)
from src.core.services.photo_processor import PhotoMetadata, PhotoProcessor


class TestScanProgress:
    """Test ScanProgress functionality."""

    def test_scan_progress_creation(self):
        """Test ScanProgress creation and initial state."""
        progress = ScanProgress()

        assert progress.total_files == 0
        assert progress.processed_files == 0
        assert progress.successful_files == 0
        assert progress.failed_files == 0
        assert progress.current_file is None
        assert progress.start_time is None
        assert progress.estimated_completion is None
        assert progress.errors == []

    def test_progress_percent_calculation(self):
        """Test progress percentage calculation."""
        progress = ScanProgress(total_files=100, processed_files=25)
        assert progress.progress_percent == 25.0

        # Test zero division
        progress = ScanProgress(total_files=0, processed_files=0)
        assert progress.progress_percent == 0.0

    def test_is_complete(self):
        """Test completion detection."""
        progress = ScanProgress(total_files=10, processed_files=10)
        assert progress.is_complete is True

        progress = ScanProgress(total_files=10, processed_files=5)
        assert progress.is_complete is False

    def test_add_error(self):
        """Test error tracking."""
        progress = ScanProgress()

        progress.add_error("Test error 1")
        progress.add_error("Test error 2")

        assert len(progress.errors) == 2
        assert "Test error 1" in progress.errors
        assert "Test error 2" in progress.errors


class TestScanOptions:
    """Test ScanOptions configuration."""

    def test_default_scan_options(self):
        """Test default scan options."""
        options = ScanOptions()

        assert options.strategy == ScanStrategy.FULL_METADATA
        assert options.recursive is True
        assert options.max_files is None
        assert options.batch_size == 50
        assert options.include_metadata is True
        assert options.include_thumbnails is False
        assert options.skip_duplicates is True
        assert options.progress_callback is None

    def test_custom_scan_options(self):
        """Test custom scan options."""
        callback = MagicMock()
        options = ScanOptions(
            strategy=ScanStrategy.FAST_METADATA_ONLY,
            recursive=False,
            max_files=100,
            batch_size=25,
            include_thumbnails=True,
            progress_callback=callback,
        )

        assert options.strategy == ScanStrategy.FAST_METADATA_ONLY
        assert options.recursive is False
        assert options.max_files == 100
        assert options.batch_size == 25
        assert options.include_thumbnails is True
        assert options.progress_callback == callback


class TestSecureDirectoryScanner:
    """Test SecureDirectoryScanner functionality."""

    @pytest.fixture
    def temp_directory(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_photos(self, temp_directory):
        """Create sample photo files for testing."""
        photos = []
        for i in range(5):
            photo_path = temp_directory / f"photo_{i}.jpg"
            # Create minimal JPEG content
            photo_path.write_bytes(
                b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
                b"\xff\xd9"  # EOI marker
            )
            photos.append(photo_path)
        return photos

    @pytest.fixture
    def mock_file_system_service(self, temp_directory, sample_photos):
        """Create mock file system service."""
        service = MagicMock(spec=SecureFileSystemService)

        # Mock get_photo_files to return sample photos
        file_entries = []
        for photo in sample_photos:
            entry = FileSystemEntry(
                path=photo,
                is_directory=False,
                size=100,
                access_level=AccessLevel.READ_ONLY,
                permissions="rw-r--r--",
                last_modified=datetime.now().timestamp(),
                is_symlink=False,
            )
            file_entries.append(entry)

        service.get_photo_files.return_value = file_entries
        service.validate_path_access.return_value = None

        return service

    @pytest.fixture
    def mock_photo_processor(self, sample_photos):
        """Create mock photo processor."""
        processor = MagicMock(spec=PhotoProcessor)

        def mock_process_photo(path):
            return PhotoMetadata(
                file_path=path,
                file_hash="mock_hash",
                file_size=100,
                mime_type="image/jpeg",
                dimensions=(100, 100),
                date_taken=datetime.now(),
                camera_make="Mock Camera",
                camera_model="Mock Model",
            )

        processor.process_photo.side_effect = mock_process_photo
        return processor

    @pytest.fixture
    def scanner(self, mock_file_system_service, mock_photo_processor):
        """Create directory scanner with mocked dependencies."""
        return SecureDirectoryScanner(
            file_system_service=mock_file_system_service,
            photo_processor=mock_photo_processor,
        )

    def test_scanner_initialization(self, mock_file_system_service):
        """Test scanner initialization."""
        scanner = SecureDirectoryScanner(file_system_service=mock_file_system_service)

        assert scanner.file_system_service == mock_file_system_service
        assert scanner.photo_processor is not None
        assert scanner._active_scans == {}

    def test_validate_scan_request_valid(self, scanner, temp_directory):
        """Test scan request validation with valid parameters."""
        options = ScanOptions()

        # Should not raise any exceptions
        scanner.validate_scan_request(temp_directory, options)

    def test_validate_scan_request_invalid_directory(self, scanner):
        """Test scan request validation with invalid directory."""
        invalid_dir = Path("/nonexistent/directory")
        options = ScanOptions()

        with pytest.raises(ValueError, match="does not exist"):
            scanner.validate_scan_request(invalid_dir, options)

    def test_validate_scan_request_invalid_options(self, scanner, temp_directory):
        """Test scan request validation with invalid options."""
        # Test negative max_files
        options = ScanOptions(max_files=-1)
        with pytest.raises(ValueError, match="max_files must be positive"):
            scanner.validate_scan_request(temp_directory, options)

        # Test negative batch_size
        options = ScanOptions(batch_size=-1)
        with pytest.raises(ValueError, match="batch_size must be positive"):
            scanner.validate_scan_request(temp_directory, options)

    def test_estimate_scan_size(self, scanner, temp_directory, sample_photos):
        """Test scan size estimation."""
        estimate = scanner.estimate_scan_size(temp_directory, recursive=True)

        assert "directory" in estimate
        assert "total_photo_files" in estimate
        assert "total_size_bytes" in estimate
        assert "estimated_duration_seconds" in estimate
        assert estimate["total_photo_files"] == len(sample_photos)

    def test_scan_directory_fast(self, scanner, temp_directory, sample_photos):
        """Test fast directory scanning."""
        options = ScanOptions(strategy=ScanStrategy.FAST_METADATA_ONLY)

        result = scanner.scan_directory_fast(temp_directory, options)

        assert isinstance(result, ScanResult)
        assert result.status == ScanStatus.COMPLETED
        assert result.strategy == ScanStrategy.FAST_METADATA_ONLY
        assert result.total_files == len(sample_photos)
        assert result.successful_files == len(sample_photos)
        assert result.failed_files == 0
        assert len(result.files) == len(sample_photos)

    def test_scan_directory_fast_with_max_files(
        self, scanner, temp_directory, sample_photos
    ):
        """Test fast scanning with file limit."""
        max_files = 3
        options = ScanOptions(
            strategy=ScanStrategy.FAST_METADATA_ONLY, max_files=max_files
        )

        result = scanner.scan_directory_fast(temp_directory, options)

        assert result.total_files == max_files
        assert len(result.files) == max_files

    def test_scan_directory_full(self, scanner, temp_directory, sample_photos):
        """Test full directory scanning with metadata extraction."""
        options = ScanOptions(strategy=ScanStrategy.FULL_METADATA)

        result = scanner.scan_directory_full(temp_directory, options)

        assert isinstance(result, ScanResult)
        assert result.status == ScanStatus.COMPLETED
        assert result.strategy == ScanStrategy.FULL_METADATA
        assert result.total_files == len(sample_photos)
        assert result.successful_files == len(sample_photos)
        assert len(result.files) == len(sample_photos)

        # Check that metadata is included
        for file_result in result.files:
            assert "metadata" in file_result
            assert "file_system_info" in file_result

    def test_scan_directory_full_with_processing_errors(
        self, scanner, temp_directory, sample_photos
    ):
        """Test full scanning with photo processing errors."""

        # Configure photo processor to raise errors for some files
        def mock_process_with_errors(path):
            if "photo_1" in str(path):
                from src.core.services.photo_processor import \
                    PhotoProcessingError

                raise PhotoProcessingError("Mock processing error")

            return PhotoMetadata(
                file_path=path,
                file_hash="mock_hash",
                file_size=100,
                mime_type="image/jpeg",
                dimensions=(100, 100),
            )

        scanner.photo_processor.process_photo.side_effect = mock_process_with_errors

        options = ScanOptions(strategy=ScanStrategy.FULL_METADATA)
        result = scanner.scan_directory_full(temp_directory, options)

        assert result.status == ScanStatus.COMPLETED
        assert result.failed_files == 1  # One file should fail
        assert result.successful_files == len(sample_photos) - 1
        assert len(result.errors) == 1

    def test_scan_directory_with_progress_callback(
        self, scanner, temp_directory, sample_photos
    ):
        """Test scanning with progress callback."""
        progress_updates = []

        def progress_callback(progress):
            progress_updates.append(
                {
                    "processed": progress.processed_files,
                    "total": progress.total_files,
                    "percent": progress.progress_percent,
                }
            )

        options = ScanOptions(
            strategy=ScanStrategy.FAST_METADATA_ONLY,
            progress_callback=progress_callback,
        )

        result = scanner.scan_directory_fast(temp_directory, options)

        assert len(progress_updates) == len(sample_photos)
        assert progress_updates[-1]["percent"] == 100.0

    def test_scan_directory_main_entry_point(self, scanner, temp_directory):
        """Test main scan_directory method."""
        # Test fast strategy
        options = ScanOptions(strategy=ScanStrategy.FAST_METADATA_ONLY)
        result = scanner.scan_directory(temp_directory, options)
        assert result.strategy == ScanStrategy.FAST_METADATA_ONLY

        # Test full strategy
        options = ScanOptions(strategy=ScanStrategy.FULL_METADATA)
        result = scanner.scan_directory(temp_directory, options)
        assert result.strategy == ScanStrategy.FULL_METADATA

        # Test incremental strategy (should fall back to full)
        options = ScanOptions(strategy=ScanStrategy.INCREMENTAL)
        result = scanner.scan_directory(temp_directory, options)
        assert result.strategy == ScanStrategy.FULL_METADATA

    def test_scan_directory_with_default_options(self, scanner, temp_directory):
        """Test scanning with default options."""
        result = scanner.scan_directory(temp_directory)

        assert result.strategy == ScanStrategy.FULL_METADATA  # Default strategy
        assert isinstance(result, ScanResult)

    def test_unknown_scan_strategy(self, scanner, temp_directory):
        """Test handling of unknown scan strategy."""
        # Create a mock enum value that doesn't exist in the current implementation
        from unittest.mock import MagicMock

        options = ScanOptions()

        # Create a mock strategy that isn't handled by the scanner
        mock_strategy = MagicMock()
        mock_strategy.value = "unknown_strategy"
        options.strategy = mock_strategy

        with pytest.raises(ValueError, match="Unknown scan strategy"):
            scanner.scan_directory(temp_directory, options)

    def test_active_scan_tracking(self, scanner, temp_directory):
        """Test active scan tracking functionality."""
        # Initially no active scans
        assert len(scanner.list_active_scans()) == 0

        # Start a scan (this will add to active scans temporarily)
        options = ScanOptions(strategy=ScanStrategy.FAST_METADATA_ONLY)
        result = scanner.scan_directory_fast(temp_directory, options)

        # After completion, should be removed from active scans
        assert len(scanner.list_active_scans()) == 0

    def test_get_scan_progress_nonexistent(self, scanner):
        """Test getting progress for nonexistent scan."""
        progress = scanner.get_scan_progress("nonexistent_scan")
        assert progress is None

    def test_cancel_scan_nonexistent(self, scanner):
        """Test cancelling nonexistent scan."""
        success = scanner.cancel_scan("nonexistent_scan")
        assert success is False

    def test_scan_security_validation(self, scanner, temp_directory):
        """Test that security validation is called."""
        scanner.file_system_service.validate_path_access.side_effect = Exception(
            "Access denied"
        )

        options = ScanOptions(strategy=ScanStrategy.FAST_METADATA_ONLY)
        result = scanner.scan_directory_fast(temp_directory, options)

        assert result.status == ScanStatus.FAILED
        assert "Access denied" in result.errors[0]

    def test_scan_with_nested_directories(self, scanner, temp_directory, sample_photos):
        """Test scanning with nested directory structure."""
        # Create nested directories with photos
        nested_dir = temp_directory / "nested" / "deep"
        nested_dir.mkdir(parents=True)

        nested_photo = nested_dir / "nested_photo.jpg"
        nested_photo.write_bytes(sample_photos[0].read_bytes())

        # Update mock to include nested photo
        nested_entry = FileSystemEntry(
            path=nested_photo,
            is_directory=False,
            size=100,
            access_level=AccessLevel.READ_ONLY,
            permissions="rw-r--r--",
            last_modified=datetime.now().timestamp(),
            is_symlink=False,
        )

        original_photos = scanner.file_system_service.get_photo_files.return_value
        scanner.file_system_service.get_photo_files.return_value = original_photos + [
            nested_entry
        ]

        options = ScanOptions(strategy=ScanStrategy.FAST_METADATA_ONLY, recursive=True)
        result = scanner.scan_directory_fast(temp_directory, options)

        assert result.total_files == len(sample_photos) + 1
        assert result.successful_files == len(sample_photos) + 1


@pytest.mark.integration
class TestDirectoryScannerIntegration:
    """Integration tests for SecureDirectoryScanner."""

    def test_real_directory_scan_integration(self):
        """Test scanning a real directory with actual file system service."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test photo
            test_photo = temp_path / "test.jpg"
            test_photo.write_bytes(
                b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
                b"\xff\xd9"
            )

            # Create real services
            constraints = SecurityConstraints(
                max_file_size_mb=1
            )  # Small limit for testing
            file_system_service = SecureFileSystemService(
                allowed_directories=[temp_path], constraints=constraints
            )

            photo_processor = PhotoProcessor(file_system_service=file_system_service)
            scanner = SecureDirectoryScanner(
                file_system_service=file_system_service, photo_processor=photo_processor
            )

            # Test fast scan
            options = ScanOptions(strategy=ScanStrategy.FAST_METADATA_ONLY)
            result = scanner.scan_directory(temp_path, options)

            assert result.status == ScanStatus.COMPLETED
            assert result.total_files >= 1
            assert len(result.files) >= 1

    def test_scanner_with_permission_errors(self):
        """Test scanner behavior with permission errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create file and remove permissions
            restricted_file = temp_path / "restricted.jpg"
            restricted_file.write_bytes(b"fake jpeg")

            # Remove read permission
            import os

            os.chmod(restricted_file, 0o000)

            try:
                constraints = SecurityConstraints()
                file_system_service = SecureFileSystemService(
                    allowed_directories=[temp_path], constraints=constraints
                )

                scanner = SecureDirectoryScanner(
                    file_system_service=file_system_service
                )

                result = scanner.scan_directory(temp_path)

                # Should complete but with no accessible files
                assert result.status == ScanStatus.COMPLETED

            finally:
                # Restore permissions for cleanup
                os.chmod(restricted_file, 0o644)
