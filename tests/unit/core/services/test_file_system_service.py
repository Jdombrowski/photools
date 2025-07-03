import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.services.file_system_service import (AccessLevel,
                                                    FileSystemEntry,
                                                    FileSystemSecurityError,
                                                    SecureFileSystemService,
                                                    SecurityConstraints)


class TestSecurityConstraints:
    """Test SecurityConstraints configuration."""

    def test_default_constraints(self):
        """Test default security constraints."""
        constraints = SecurityConstraints()

        assert constraints.max_file_size_mb == 500
        assert constraints.max_depth == 10
        assert constraints.follow_symlinks is False
        assert constraints.skip_hidden_files is True
        assert constraints.skip_hidden_directories is True
        assert ".jpg" in constraints.allowed_extensions
        assert ".png" in constraints.allowed_extensions

    def test_custom_constraints(self):
        """Test custom security constraints."""
        custom_extensions = {".jpg", ".png"}
        constraints = SecurityConstraints(
            max_file_size_mb=100,
            allowed_extensions=custom_extensions,
            max_depth=5,
            follow_symlinks=True,
            skip_hidden_files=False,
        )

        assert constraints.max_file_size_mb == 100
        assert constraints.allowed_extensions == custom_extensions
        assert constraints.max_depth == 5
        assert constraints.follow_symlinks is True
        assert constraints.skip_hidden_files is False


class TestSecureFileSystemService:
    """Test SecureFileSystemService functionality and security."""

    @pytest.fixture
    def temp_directory(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_photo(self, temp_directory):
        """Create a sample photo file for testing."""
        photo_path = temp_directory / "test_photo.jpg"
        # Create a small valid JPEG file
        photo_path.write_bytes(
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
            b"\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01"
            b"\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff"
            b"\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9"
        )
        return photo_path

    @pytest.fixture
    def large_file(self, temp_directory):
        """Create a large file for size testing."""
        large_file = temp_directory / "large_file.jpg"
        # Create a file larger than default limit (500MB)
        large_file.write_bytes(b"x" * (600 * 1024 * 1024))  # 600MB
        return large_file

    @pytest.fixture
    def hidden_file(self, temp_directory):
        """Create a hidden file for testing."""
        hidden_file = temp_directory / ".hidden_photo.jpg"
        hidden_file.write_bytes(b"fake jpeg content")
        return hidden_file

    @pytest.fixture
    def service(self, temp_directory):
        """Create SecureFileSystemService with test directory."""
        return SecureFileSystemService(
            allowed_directories=[temp_directory], constraints=SecurityConstraints()
        )

    def test_service_initialization_valid_directory(self, temp_directory):
        """Test service initialization with valid directory."""
        service = SecureFileSystemService(allowed_directories=[temp_directory])
        assert len(service.allowed_directories) == 1
        assert service.allowed_directories[0] == temp_directory.resolve()

    def test_service_initialization_invalid_directory(self):
        """Test service initialization with invalid directory."""
        invalid_dir = Path("/nonexistent/directory")

        with pytest.raises(FileSystemSecurityError, match="does not exist"):
            SecureFileSystemService(allowed_directories=[invalid_dir])

    def test_path_normalization(self, service, temp_directory):
        """Test path normalization and resolution."""
        # Test relative path resolution
        relative_path = temp_directory / "subdir" / ".." / "file.jpg"
        normalized = service._normalize_path(relative_path)
        expected = temp_directory / "file.jpg"
        assert normalized == expected.resolve()

    def test_path_access_allowed(self, service, temp_directory, sample_photo):
        """Test access to allowed paths."""
        assert service.validate_path_access(sample_photo) is True
        assert service.validate_path_access(temp_directory) is True

    def test_path_access_denied_outside_allowed(self, service):
        """Test access denial for paths outside allowed directories."""
        outside_path = Path("/tmp/outside_file.jpg")

        with pytest.raises(FileSystemSecurityError, match="not in allowed directories"):
            service.validate_path_access(outside_path)

    def test_path_traversal_attack_prevention(self, service, temp_directory):
        """Test prevention of path traversal attacks."""
        # Attempt to access parent directory using path traversal
        traversal_path = temp_directory / ".." / ".." / "etc" / "passwd"

        with pytest.raises(FileSystemSecurityError, match="not in allowed directories"):
            service.validate_path_access(traversal_path)

    def test_symlink_handling_disabled(self, service, temp_directory, sample_photo):
        """Test symlink handling when disabled."""
        symlink_path = temp_directory / "photo_symlink.jpg"
        os.symlink(sample_photo, symlink_path)

        with pytest.raises(FileSystemSecurityError, match="Symlinks not allowed"):
            service.validate_path_access(symlink_path)

    def test_symlink_handling_enabled(self, temp_directory, sample_photo):
        """Test symlink handling when enabled."""
        constraints = SecurityConstraints(follow_symlinks=True)
        service = SecureFileSystemService(
            allowed_directories=[temp_directory], constraints=constraints
        )

        symlink_path = temp_directory / "photo_symlink.jpg"
        os.symlink(sample_photo, symlink_path)

        assert service.validate_path_access(symlink_path) is True

    def test_hidden_file_handling_disabled(self, service, hidden_file):
        """Test hidden file handling when disabled."""
        with pytest.raises(FileSystemSecurityError, match="Hidden files not allowed"):
            service.validate_path_access(hidden_file)

    def test_hidden_file_handling_enabled(self, temp_directory, hidden_file):
        """Test hidden file handling when enabled."""
        constraints = SecurityConstraints(skip_hidden_files=False)
        service = SecureFileSystemService(
            allowed_directories=[temp_directory], constraints=constraints
        )

        assert service.validate_path_access(hidden_file) is True

    def test_file_size_constraint_small_file(self, service, sample_photo):
        """Test file size constraint with small file."""
        access_level = service._check_file_constraints(sample_photo)
        assert access_level == AccessLevel.READ_ONLY

    def test_file_size_constraint_large_file(self, service, large_file):
        """Test file size constraint with large file."""
        access_level = service._check_file_constraints(large_file)
        assert access_level == AccessLevel.NO_ACCESS

    def test_file_extension_allowed(self, service, sample_photo):
        """Test allowed file extension."""
        access_level = service._check_file_constraints(sample_photo)
        assert access_level == AccessLevel.READ_ONLY

    def test_file_extension_not_allowed(self, service, temp_directory):
        """Test disallowed file extension."""
        txt_file = temp_directory / "document.txt"
        txt_file.write_text("This is not a photo")

        access_level = service._check_file_constraints(txt_file)
        assert access_level == AccessLevel.NO_ACCESS

    def test_get_file_info_valid_file(self, service, sample_photo):
        """Test getting file info for valid file."""
        file_info = service.get_file_info(sample_photo)

        assert file_info.path == sample_photo.resolve()
        assert file_info.is_directory is False
        assert file_info.access_level == AccessLevel.READ_ONLY
        assert file_info.size > 0
        assert file_info.error is None

    def test_get_file_info_nonexistent_file(self, service, temp_directory):
        """Test getting file info for nonexistent file."""
        nonexistent = temp_directory / "nonexistent.jpg"
        file_info = service.get_file_info(nonexistent)

        assert file_info.access_level == AccessLevel.NO_ACCESS
        assert file_info.error == "File not found"

    def test_get_file_info_directory(self, service, temp_directory):
        """Test getting file info for directory."""
        file_info = service.get_file_info(temp_directory)

        assert file_info.is_directory is True
        assert file_info.access_level == AccessLevel.READ_ONLY
        assert file_info.error is None

    def test_list_directory_non_recursive(self, service, temp_directory, sample_photo):
        """Test non-recursive directory listing."""
        entries = service.list_directory(temp_directory, recursive=False)

        assert len(entries) == 1
        assert entries[0].path == sample_photo.resolve()
        assert entries[0].access_level == AccessLevel.READ_ONLY

    def test_list_directory_recursive(self, service, temp_directory, sample_photo):
        """Test recursive directory listing."""
        # Create subdirectory with photo
        subdir = temp_directory / "subdir"
        subdir.mkdir()
        sub_photo = subdir / "sub_photo.jpg"
        sub_photo.write_bytes(sample_photo.read_bytes())

        entries = service.list_directory(temp_directory, recursive=True)

        assert len(entries) >= 2  # At least the two photos
        photo_paths = [entry.path for entry in entries if not entry.is_directory]
        assert sample_photo.resolve() in photo_paths
        assert sub_photo.resolve() in photo_paths

    def test_list_directory_max_depth(self, service, temp_directory, sample_photo):
        """Test directory listing with depth limit."""
        # Create nested structure
        deep_dir = temp_directory / "level1" / "level2" / "level3"
        deep_dir.mkdir(parents=True)
        deep_photo = deep_dir / "deep_photo.jpg"
        deep_photo.write_bytes(sample_photo.read_bytes())

        # List with max_depth=2
        entries = service.list_directory(temp_directory, recursive=True, max_depth=2)

        # Should not include the deep photo (level 3)
        photo_paths = [entry.path for entry in entries if not entry.is_directory]
        assert deep_photo.resolve() not in photo_paths
        assert sample_photo.resolve() in photo_paths

    def test_get_photo_files(self, service, temp_directory, sample_photo):
        """Test getting photo files specifically."""
        # Create non-photo file
        txt_file = temp_directory / "readme.txt"
        txt_file.write_text("Not a photo")

        photo_files = service.get_photo_files(temp_directory)

        assert len(photo_files) == 1
        assert photo_files[0].path == sample_photo.resolve()
        assert all(not entry.is_directory for entry in photo_files)

    def test_get_directory_stats(self, service, temp_directory, sample_photo):
        """Test getting directory statistics."""
        stats = service.get_directory_stats(temp_directory)

        assert stats["directory"] == str(temp_directory)
        assert stats["total_files"] == 1
        assert stats["total_size_bytes"] > 0
        assert stats["total_size_mb"] > 0
        assert ".jpg" in stats["file_extensions"]
        assert stats["file_extensions"][".jpg"] == 1

    def test_permission_handling(self, service, temp_directory):
        """Test handling of permission errors."""
        # Create file and remove read permission
        restricted_file = temp_directory / "restricted.jpg"
        restricted_file.write_bytes(b"fake jpeg")

        # Remove read permission
        os.chmod(restricted_file, 0o000)

        try:
            access_level = service._check_file_constraints(restricted_file)
            assert access_level == AccessLevel.NO_ACCESS
        finally:
            # Restore permission for cleanup
            os.chmod(restricted_file, 0o644)

    def test_error_handling_invalid_path(self, service):
        """Test error handling for invalid paths."""
        # Test with special characters and invalid paths
        invalid_paths = [
            Path("\x00invalid"),
            Path("con"),  # Reserved name on Windows
        ]

        for invalid_path in invalid_paths:
            try:
                service._normalize_path(invalid_path)
            except FileSystemSecurityError:
                pass  # Expected for some invalid paths

    def test_concurrent_access(self, service, temp_directory, sample_photo):
        """Test concurrent access to the service."""
        import threading
        import time

        results = []
        errors = []

        def access_file():
            try:
                file_info = service.get_file_info(sample_photo)
                results.append(file_info.access_level)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=access_file)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Check results
        assert len(errors) == 0
        assert len(results) == 10
        assert all(level == AccessLevel.READ_ONLY for level in results)


class TestFileSystemEntry:
    """Test FileSystemEntry data class."""

    def test_file_system_entry_creation(self):
        """Test FileSystemEntry creation and properties."""
        path = Path("/test/photo.jpg")
        entry = FileSystemEntry(
            path=path,
            is_directory=False,
            size=1024,
            access_level=AccessLevel.READ_ONLY,
            permissions="rw-r--r--",
            last_modified=1234567890.0,
            is_symlink=False,
        )

        assert entry.path == path
        assert entry.is_directory is False
        assert entry.size == 1024
        assert entry.access_level == AccessLevel.READ_ONLY
        assert entry.permissions == "rw-r--r--"
        assert entry.last_modified == 1234567890.0
        assert entry.is_symlink is False
        assert entry.error is None

    def test_file_system_entry_with_error(self):
        """Test FileSystemEntry with error information."""
        entry = FileSystemEntry(
            path=Path("/test/error.jpg"),
            is_directory=False,
            size=0,
            access_level=AccessLevel.NO_ACCESS,
            permissions="",
            last_modified=0,
            error="Permission denied",
        )

        assert entry.access_level == AccessLevel.NO_ACCESS
        assert entry.error == "Permission denied"


@pytest.mark.integration
class TestFileSystemServiceIntegration:
    """Integration tests for SecureFileSystemService."""

    def test_real_directory_scan(self):
        """Test scanning a real directory structure."""
        # Use the current project directory for testing
        project_root = Path(__file__).parent.parent.parent.parent.parent

        # Only test if we can access the project directory
        if not project_root.exists():
            pytest.skip("Project directory not accessible")

        service = SecureFileSystemService(
            allowed_directories=[project_root],
            constraints=SecurityConstraints(max_depth=2),  # Limit depth for performance
        )

        # Test listing project directory
        entries = service.list_directory(project_root, recursive=False)
        assert len(entries) > 0

        # Test directory stats (should handle mixed file types)
        stats = service.get_directory_stats(project_root)
        assert "directory" in stats
        assert "total_files" in stats
