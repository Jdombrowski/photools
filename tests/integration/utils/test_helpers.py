"""
Test utilities and helper functions for Photools testing.

Provides clean abstractions for testing business logic without coupling
to specific implementations.
"""

import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from PIL import Image

from src.core.services.directory_scanner import SecureDirectoryScanner
from src.core.services.file_system_service import SecureFileSystemService
from src.core.services.photo_processor import PhotoProcessor
from tests.integration.config.test_settings import TestingEnvironment


class TestPhotoFactory:
    """Factory for creating test photo files."""

    @staticmethod
    def create_test_photo(
        path: Path,
        width: int = 100,
        height: int = 100,
        format: str = "JPEG",
        color: str = "red",
    ) -> Path:
        """Create a test photo file at the specified path."""
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create image
        img = Image.new("RGB", (width, height), color=color)

        # Save image
        img.save(path, format)

        return path

    @staticmethod
    def create_test_photos_batch(
        directory: Path, count: int = 5, prefix: str = "test_photo"
    ) -> list[Path]:
        """Create a batch of test photos in a directory."""
        directory.mkdir(parents=True, exist_ok=True)

        photos = []
        for i in range(count):
            photo_path = directory / f"{prefix}_{i:03d}.jpg"
            TestPhotoFactory.create_test_photo(
                photo_path,
                width=100 + i * 10,
                height=100 + i * 10,
                color=["red", "green", "blue", "yellow", "purple"][i % 5],
            )
            photos.append(photo_path)

        return photos


class FileSystemBuilder:
    """Builder for creating test file system scenarios."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def add_photos(self, subdir: str = "", count: int = 3) -> "FileSystemBuilder":
        """Add photos to the test file system."""
        target_dir = self.base_dir / subdir if subdir else self.base_dir
        TestPhotoFactory.create_test_photos_batch(target_dir, count)
        return self

    def add_nested_structure(self) -> "FileSystemBuilder":
        """Add a nested directory structure with photos."""
        structure = {
            "level1/photos": 3,
            "level1/level2/photos": 2,
            "level1/level2/level3/photos": 1,
        }

        for subdir, count in structure.items():
            self.add_photos(subdir, count)

        return self

    def add_non_photo_files(self) -> "FileSystemBuilder":
        """Add non-photo files for testing filtering."""
        files = [
            ("readme.txt", "This is a text file"),
            ("script.py", "print('hello world')"),
            ("config.json", '{"test": true}'),
        ]

        for filename, content in files:
            file_path = self.base_dir / filename
            file_path.write_text(content)

        return self

    def build(self) -> Path:
        """Return the built directory structure."""
        return self.base_dir


@contextmanager
def temporary_test_directory() -> Generator[Path, None, None]:
    """Context manager for temporary test directories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@contextmanager
def isolated_test_environment() -> Generator[TestingEnvironment, None, None]:
    """Context manager for isolated test environment."""
    with TestingEnvironment() as test_env:
        yield test_env


class ServiceTestBuilder:
    """Builder for creating configured services for testing."""

    def __init__(self, test_env: TestingEnvironment):
        self.test_env = test_env

    def build_file_system_service(
        self, allowed_directories: list[Path] | None = None
    ) -> SecureFileSystemService:
        """Build a configured file system service for testing."""
        if allowed_directories is None:
            allowed_directories = self.test_env.get_allowed_directories()

        constraints = self.test_env.security.to_security_constraints()

        return SecureFileSystemService(
            allowed_directories=allowed_directories, constraints=constraints
        )

    def build_photo_processor(
        self, file_system_service: SecureFileSystemService | None = None
    ) -> PhotoProcessor:
        """Build a configured photo processor for testing."""
        if file_system_service is None:
            file_system_service = self.build_file_system_service()

        return PhotoProcessor(
            file_system_service=file_system_service,
            max_file_size_mb=self.test_env.security.max_file_size_mb,
        )

    def build_directory_scanner(
        self,
        file_system_service: SecureFileSystemService | None = None,
        photo_processor: PhotoProcessor | None = None,
    ) -> SecureDirectoryScanner:
        """Build a configured directory scanner for testing."""
        if file_system_service is None:
            file_system_service = self.build_file_system_service()

        if photo_processor is None:
            photo_processor = self.build_photo_processor(file_system_service)

        return SecureDirectoryScanner(
            file_system_service=file_system_service, photo_processor=photo_processor
        )


class TestAssertions:
    """Custom assertions for testing Photools functionality."""

    @staticmethod
    def assert_security_violation_blocked(func, *args, **kwargs):
        """Assert that a function raises a security violation."""
        from src.core.services.file_system_service import \
            FileSystemSecurityError

        try:
            result = func(*args, **kwargs)
            raise AssertionError(
                f"Expected security violation, but function succeeded: {result}"
            )
        except FileSystemSecurityError:
            # Expected - security violation properly blocked
            pass
        except Exception as e:
            raise AssertionError(
                f"Expected FileSystemSecurityError, but got {type(e).__name__}: {e}"
            )

    @staticmethod
    def assert_photos_discovered(
        file_system_service: SecureFileSystemService,
        directory: Path,
        expected_count: int,
        tolerance: int = 0,
    ):
        """Assert that the expected number of photos were discovered."""
        photos = file_system_service.get_photo_files(directory, recursive=True)
        actual_count = len(photos)

        if abs(actual_count - expected_count) > tolerance:
            raise AssertionError(
                f"Expected {expected_count} ± {tolerance} photos, but found {actual_count}"
            )

    @staticmethod
    def assert_metadata_extracted(
        metadata_dict: dict[str, Any], required_fields: list[str]
    ):
        """Assert that metadata contains required fields."""
        missing_fields = [
            field for field in required_fields if field not in metadata_dict
        ]

        if missing_fields:
            raise AssertionError(f"Missing required metadata fields: {missing_fields}")

    @staticmethod
    def assert_scan_successful(scan_result, min_success_rate: float = 0.8):
        """Assert that a scan result meets success criteria."""
        from src.core.models.scan_result import ScanStatus

        if scan_result.status != ScanStatus.COMPLETED:
            raise AssertionError(f"Scan not completed: {scan_result.status}")

        if scan_result.success_rate < min_success_rate * 100:
            raise AssertionError(
                f"Scan success rate too low: {scan_result.success_rate}% < {min_success_rate * 100}%"
            )


class ReportGenerator:
    """Utility for generating test reports."""

    def __init__(self):
        self.results = []

    def add_result(self, test_name: str, passed: bool, details: str = ""):
        """Add a test result."""
        self.results.append(
            {"test_name": test_name, "passed": passed, "details": details}
        )

    def print_summary(self):
        """Print test summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])

        print(f"\n{'='*60}")
        print(f"Test Summary: {passed}/{total} tests passed")
        print(f"{'='*60}")

        for result in self.results:
            status = "✅" if result["passed"] else "❌"
            print(f"{status} {result['test_name']}")
            if result["details"]:
                print(f"   {result['details']}")

        print(f"{'='*60}")

        return passed == total

    def get_success_rate(self) -> float:
        """Get success rate as percentage."""
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r["passed"]) / len(self.results) * 100
