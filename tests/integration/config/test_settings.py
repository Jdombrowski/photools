"""
Test configuration management for Photools.

This module provides configuration specifically for testing environments,
separate from production business logic.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from src.core.services.file_system_service import SecurityConstraints


@dataclass
class TestingPaths:
    """Test-specific path configuration."""

    project_root: Path
    test_photos_dir: Path
    test_fixtures_dir: Path
    test_output_dir: Path

    @classmethod
    def create_default(cls) -> "TestingPaths":
        """Create default test paths relative to project root."""
        project_root = Path(__file__).parent.parent.parent
        return cls(
            project_root=project_root,
            test_photos_dir=project_root / "data" / "test_photos",
            test_fixtures_dir=project_root / "tests" / "fixtures",
            test_output_dir=project_root / "tests" / "output",
        )

    def ensure_directories_exist(self) -> None:
        """Ensure all test directories exist."""
        for attr_name in ["test_fixtures_dir", "test_output_dir"]:
            directory = getattr(self, attr_name)
            directory.mkdir(parents=True, exist_ok=True)


@dataclass
class TestingSecurityConfig:
    """Security configuration for testing."""

    max_file_size_mb: int = 50  # Smaller for tests
    max_directory_depth: int = 3  # Shallower for tests
    allowed_extensions: set = None
    strict_validation: bool = True
    log_violations: bool = True

    def __post_init__(self):
        if self.allowed_extensions is None:
            # Only common photo extensions for testing
            self.allowed_extensions = {
                ".jpg",
                ".jpeg",
                ".png",
                ".tiff",
                ".tif",
                ".bmp",
                ".webp",
            }

    def to_security_constraints(self) -> SecurityConstraints:
        """Convert to SecurityConstraints for business logic."""
        return SecurityConstraints(
            max_file_size_mb=self.max_file_size_mb,
            max_depth=self.max_directory_depth,
            allowed_extensions=self.allowed_extensions,
            follow_symlinks=False,
            skip_hidden_files=True,
            skip_hidden_directories=True,
            max_path_length=1024,
            block_executable_extensions=self.strict_validation,
            strict_extension_validation=self.strict_validation,
            enable_symlink_escape_detection=True,
            log_security_violations=self.log_violations,
        )


class TestingEnvironment:
    """Manages test environment configuration and setup."""

    def __init__(self, use_test_photos: bool = True):
        self.paths = TestingPaths.create_default()
        self.security = TestingSecurityConfig()
        self.use_test_photos = use_test_photos

        # Ensure test directories exist
        self.paths.ensure_directories_exist()

    def get_allowed_directories(self) -> list[Path]:
        """Get list of directories allowed for testing."""
        directories = []

        if self.use_test_photos and self.paths.test_photos_dir.exists():
            directories.append(self.paths.test_photos_dir)

        # Add fixtures directory for controlled testing
        if self.paths.test_fixtures_dir.exists():
            directories.append(self.paths.test_fixtures_dir)

        return directories

    def setup_test_environment(self) -> None:
        """Set up environment variables for testing."""
        # Override environment variables for testing
        test_env = {
            "ENVIRONMENT": "testing",
            "API_DEBUG": "true",
            "LOG_LEVEL": "DEBUG",
            "PHOTO_MAX_FILE_SIZE_MB": str(self.security.max_file_size_mb),
            "PHOTO_MAX_DIRECTORY_DEPTH": str(self.security.max_directory_depth),
            "PHOTO_FOLLOW_SYMLINKS": "false",
            "PHOTO_STRICT_PATH_VALIDATION": str(
                self.security.strict_validation
            ).lower(),
            "PHOTO_LOG_SECURITY_VIOLATIONS": str(self.security.log_violations).lower(),
        }

        # Set allowed directories
        if self.get_allowed_directories():
            dirs_str = ",".join(str(d) for d in self.get_allowed_directories())
            test_env["PHOTO_ALLOWED_PHOTO_DIRECTORIES"] = dirs_str

        # Apply environment variables
        for key, value in test_env.items():
            os.environ[key] = value

    def cleanup_test_environment(self) -> None:
        """Clean up test environment variables."""
        test_keys = [
            "ENVIRONMENT",
            "API_DEBUG",
            "LOG_LEVEL",
            "PHOTO_MAX_FILE_SIZE_MB",
            "PHOTO_MAX_DIRECTORY_DEPTH",
            "PHOTO_FOLLOW_SYMLINKS",
            "PHOTO_STRICT_PATH_VALIDATION",
            "PHOTO_LOG_SECURITY_VIOLATIONS",
            "PHOTO_ALLOWED_PHOTO_DIRECTORIES",
        ]

        for key in test_keys:
            os.environ.pop(key, None)

    def get_test_photo_count(self) -> int:
        """Get count of test photos available."""
        if not self.paths.test_photos_dir.exists():
            return 0

        photo_extensions = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}
        count = 0

        for file_path in self.paths.test_photos_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in photo_extensions:
                count += 1

        return count

    def __enter__(self):
        """Context manager entry - setup test environment."""
        self.setup_test_environment()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup test environment."""
        self.cleanup_test_environment()


# Global test environment instance for convenience
_test_env: TestingEnvironment | None = None


def get_test_environment(use_test_photos: bool = True) -> TestingEnvironment:
    """Get or create the global test environment."""
    global _test_env
    if _test_env is None:
        _test_env = TestingEnvironment(use_test_photos=use_test_photos)
    return _test_env


def reset_test_environment():
    """Reset the global test environment."""
    global _test_env
    if _test_env:
        _test_env.cleanup_test_environment()
    _test_env = None


def isolated_test_environment():
    """Context manager for isolated test environment."""
    return TestingEnvironment()
