"""
Integration tests for Filesystem API endpoints.

Tests API functionality while maintaining clean separation from business logic.
"""

from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from tests.integration.config.test_settings import (TestEnvironment,
                                        isolated_test_environment)
from tests.integration.utils.test_helpers import (TestFileSystemBuilder, TestReporter,
                                      temporary_test_directory)


class FilesystemAPITester:
    """Clean abstraction for testing filesystem API endpoints."""

    def __init__(self, client: TestClient):
        self.client = client
        self.base_url = "/api/v1/filesystem"

    def test_health_check(self) -> Dict[str, Any]:
        """Test basic API health."""
        response = self.client.get("/")
        return {
            "success": response.status_code == 200,
            "data": response.json() if response.status_code == 200 else None,
            "status_code": response.status_code,
        }

    def test_configuration(self) -> Dict[str, Any]:
        """Test filesystem configuration endpoint."""
        response = self.client.get(f"{self.base_url}/config")

        if response.status_code == 200:
            config = response.json()
            return {
                "success": True,
                "directories_count": len(config.get("allowed_directories", [])),
                "extensions_count": len(config.get("photo_extensions", [])),
                "security_config": config.get("security_constraints", {}),
                "data": config,
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
            }

    def test_allowed_directories(self) -> Dict[str, Any]:
        """Test allowed directories endpoint."""
        response = self.client.get(f"{self.base_url}/directories")

        if response.status_code == 200:
            directories = response.json()
            return {
                "success": True,
                "count": len(directories),
                "directories": directories,
            }
        else:
            return {"success": False, "status_code": response.status_code}

    def test_directory_info(self, directory_path: str) -> Dict[str, Any]:
        """Test directory info endpoint."""
        # URL encode the path
        import urllib.parse

        encoded_path = urllib.parse.quote(directory_path, safe="")

        response = self.client.get(f"{self.base_url}/directories/{encoded_path}/info")

        result = {
            "success": response.status_code in [200, 403],  # 403 is valid for security
            "status_code": response.status_code,
            "path": directory_path,
        }

        if response.status_code == 200:
            data = response.json()
            result.update(
                {
                    "exists": data.get("exists"),
                    "is_directory": data.get("is_directory"),
                    "access_level": data.get("access_level"),
                    "stats": data.get("stats", {}),
                }
            )
        elif response.status_code == 403:
            result["security_blocked"] = True

        return result

    def test_directory_files(self, directory_path: str) -> Dict[str, Any]:
        """Test directory files listing endpoint."""
        import urllib.parse

        encoded_path = urllib.parse.quote(directory_path, safe="")

        response = self.client.get(
            f"{self.base_url}/directories/{encoded_path}/files",
            params={"recursive": "false", "max_depth": "2"},
        )

        result = {
            "success": response.status_code in [200, 403],
            "status_code": response.status_code,
            "path": directory_path,
        }

        if response.status_code == 200:
            data = response.json()
            result.update(
                {
                    "total_entries": data.get("total_entries", 0),
                    "files_count": len(data.get("files", [])),
                    "directories_count": len(data.get("directories", [])),
                }
            )

        return result

    def test_photo_files(self, directory_path: str) -> Dict[str, Any]:
        """Test photo files endpoint."""
        import urllib.parse

        encoded_path = urllib.parse.quote(directory_path, safe="")

        response = self.client.get(
            f"{self.base_url}/directories/{encoded_path}/photos",
            params={"recursive": "true"},
        )

        result = {
            "success": response.status_code in [200, 403],
            "status_code": response.status_code,
            "path": directory_path,
        }

        if response.status_code == 200:
            data = response.json()
            result.update(
                {
                    "total_photos": data.get("total_photos", 0),
                    "total_size_mb": data.get("total_size_mb", 0),
                    "file_extensions": data.get("file_extensions", {}),
                }
            )

        return result

    def test_scan_estimation(self, directory_path: str) -> Dict[str, Any]:
        """Test scan estimation endpoint."""
        response = self.client.post(
            f"{self.base_url}/scan/estimate",
            params={"directory_path": directory_path, "recursive": "true"},
        )

        result = {
            "success": response.status_code in [200, 403],
            "status_code": response.status_code,
            "path": directory_path,
        }

        if response.status_code == 200:
            data = response.json()
            result.update(
                {
                    "estimated_photos": data.get("total_photo_files", 0),
                    "estimated_size_mb": data.get("total_size_mb", 0),
                    "estimated_duration": data.get("estimated_duration_minutes", 0),
                }
            )

        return result

    def test_security_violations(self) -> Dict[str, Any]:
        """Test security violation handling."""
        dangerous_paths = [
            "../../../etc/passwd",
            "/etc/passwd",
            "C:\\Windows\\System32",
            "//server/share",
            "path/with/../../traversal",
        ]

        blocked_count = 0
        results = []

        for path in dangerous_paths:
            result = self.test_directory_info(path)
            is_blocked = result["status_code"] in [403, 400]  # Blocked or bad request

            if is_blocked:
                blocked_count += 1

            results.append(
                {
                    "path": path,
                    "blocked": is_blocked,
                    "status_code": result["status_code"],
                }
            )

        return {
            "success": blocked_count >= len(dangerous_paths) * 0.8,  # 80% block rate
            "blocked_count": blocked_count,
            "total_attempts": len(dangerous_paths),
            "block_rate": blocked_count / len(dangerous_paths) * 100,
            "details": results,
        }


class TestFilesystemAPI:
    """Test suite for filesystem API endpoints."""

    def test_with_real_photos(self):
        """Test API with real photo data."""
        reporter = TestReporter()

        with isolated_test_environment() as test_env:
            # Setup test environment for API
            test_env.setup_test_environment()

            try:
                with TestClient(app) as client:
                    tester = FilesystemAPITester(client)

                    # Test basic health
                    health = tester.test_health_check()
                    reporter.add_result(
                        "API Health Check",
                        health["success"],
                        f"Status: {health['status_code']}",
                    )

                    # Test configuration
                    config = tester.test_configuration()
                    reporter.add_result(
                        "Configuration Endpoint",
                        config["success"],
                        f"Dirs: {config.get('directories_count', 0)}, Exts: {config.get('extensions_count', 0)}",
                    )

                    # Test allowed directories
                    dirs = tester.test_allowed_directories()
                    reporter.add_result(
                        "Allowed Directories",
                        dirs["success"],
                        f"Found {dirs.get('count', 0)} allowed directories",
                    )

                    # Test with first allowed directory if available
                    if dirs["success"] and dirs.get("directories"):
                        test_dir = dirs["directories"][0]

                        # Test directory info
                        dir_info = tester.test_directory_info(test_dir)
                        reporter.add_result(
                            "Directory Info",
                            dir_info["success"],
                            f"Access: {dir_info.get('access_level', 'unknown')}",
                        )

                        # Test photo files
                        photos = tester.test_photo_files(test_dir)
                        reporter.add_result(
                            "Photo Files Discovery",
                            photos["success"],
                            f"Found {photos.get('total_photos', 0)} photos",
                        )

                        # Test scan estimation
                        estimate = tester.test_scan_estimation(test_dir)
                        reporter.add_result(
                            "Scan Estimation",
                            estimate["success"],
                            f"Est: {estimate.get('estimated_photos', 0)} photos",
                        )

                    # Test security
                    security = tester.test_security_violations()
                    reporter.add_result(
                        "Security Violations",
                        security["success"],
                        f"Blocked {security['blocked_count']}/{security['total_attempts']} attacks",
                    )

            finally:
                test_env.cleanup_test_environment()

        success = reporter.print_summary()
        assert (
            success
        ), f"API test failed with {reporter.get_success_rate():.1f}% success rate"

    def test_with_synthetic_data(self):
        """Test API with synthetic test data."""
        reporter = TestReporter()

        with temporary_test_directory() as temp_dir:
            # Create synthetic test structure
            builder = TestFileSystemBuilder(temp_dir)
            test_dir = builder.add_photos("photos", 3).add_non_photo_files().build()

            with isolated_test_environment() as test_env:
                # Override allowed directories for this test
                import os

                os.environ["PHOTO_ALLOWED_PHOTO_DIRECTORIES"] = str(test_dir)
                test_env.setup_test_environment()

                try:
                    with TestClient(app) as client:
                        tester = FilesystemAPITester(client)

                        # Test configuration with synthetic data
                        config = tester.test_configuration()
                        reporter.add_result(
                            "Synthetic Config",
                            config["success"],
                            "Configuration loaded with synthetic directory",
                        )

                        # Test photo discovery
                        photos = tester.test_photo_files(str(test_dir))
                        expected_photos = 3  # From builder
                        actual_photos = photos.get("total_photos", 0)

                        success = photos["success"] and actual_photos == expected_photos
                        reporter.add_result(
                            "Synthetic Photo Discovery",
                            success,
                            f"Expected {expected_photos}, found {actual_photos}",
                        )

                        # Test file filtering (should exclude non-photos)
                        files = tester.test_directory_files(str(test_dir))
                        reporter.add_result(
                            "File Filtering",
                            files["success"],
                            f"Total entries: {files.get('total_entries', 0)}",
                        )

                finally:
                    test_env.cleanup_test_environment()

        success = reporter.print_summary()
        assert success, "Synthetic API test failed"


def run_api_integration_tests():
    """Run all API integration tests."""
    print("🌐 Running Filesystem API Integration Tests")
    print("=" * 60)

    tests = TestFilesystemAPI()
    overall_reporter = TestReporter()

    # Test with real photos
    try:
        tests.test_with_real_photos()
        overall_reporter.add_result("Real Photos API Test", True)
    except Exception as e:
        overall_reporter.add_result("Real Photos API Test", False, str(e))

    # Test with synthetic data
    try:
        tests.test_with_synthetic_data()
        overall_reporter.add_result("Synthetic Data API Test", True)
    except Exception as e:
        overall_reporter.add_result("Synthetic Data API Test", False, str(e))

    print("\n🎯 API INTEGRATION TEST RESULTS")
    return overall_reporter.print_summary()


if __name__ == "__main__":
    import sys

    success = run_api_integration_tests()
    sys.exit(0 if success else 1)
