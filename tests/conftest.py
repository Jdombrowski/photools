"""
Shared pytest configuration and fixtures.

This file is automatically discovered by pytest and provides
configuration and fixtures available to all tests.
"""

import os
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def project_root_path() -> Path:
    """Provide path to project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_data_dir(project_root_path: Path) -> Path:
    """Provide path to test data directory."""
    return project_root_path / "data" / "test_photos"


@pytest.fixture
def temp_directory() -> Generator[Path, None, None]:
    """Provide a clean temporary directory for each test."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture(scope="session")
def test_env_vars():
    """Set test environment variables."""
    original_env = os.environ.copy()

    # Set test-specific environment variables
    test_env = {
        "ENVIRONMENT": "testing",
        "DEBUG": "true",
        "DATABASE_URL": "sqlite:///:memory:",
        "REDIS_URL": "redis://localhost:6378/15",  # Use test DB
        "PHOTO_ALLOWED_PHOTO_DIRECTORIES_STR": "/tmp/test_photos,/tmp/test_uploads",
    }

    os.environ.update(test_env)

    yield test_env

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(autouse=True)
def clean_environment():
    """Ensure clean environment for each test."""
    # Clear any cached settings
    from src.config.settings import reload_settings

    reload_settings()

    yield

    # Clean up after test
    reload_settings()


# Configure pytest markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


# Test collection configuration
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Auto-mark tests based on their location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
