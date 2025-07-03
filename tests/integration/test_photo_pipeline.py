"""
Integration tests for the complete photo processing pipeline.

Tests the entire flow from directory scanning to metadata extraction
using clean architecture principles.
"""

from pathlib import Path

import pytest

from src.core.models.scan_result import ScanOptions, ScanStrategy
from tests.integration.config.test_settings import TestEnvironment
from tests.integration.utils.test_helpers import (ServiceTestBuilder, TestAssertions,
                                      TestFileSystemBuilder, TestReporter,
                                      isolated_test_environment,
                                      temporary_test_directory)


class TestPhotoProcessingPipeline:
    """Test the complete photo processing pipeline."""

    def test_pipeline_with_real_photos(self):
        """Test the pipeline using real photos from test data."""
        reporter = TestReporter()

        with isolated_test_environment() as test_env:
            # Check if we have real test photos
            photo_count = test_env.get_test_photo_count()
            if photo_count == 0:
                pytest.skip("No test photos available")

            reporter.add_result(
                "Test Environment Setup", True, f"Found {photo_count} test photos"
            )

            # Build services
            builder = ServiceTestBuilder(test_env)
            file_service = builder.build_file_system_service()
            photo_processor = builder.build_photo_processor(file_service)
            scanner = builder.build_directory_scanner(file_service, photo_processor)

            reporter.add_result(
                "Service Creation", True, "All services created successfully"
            )

            # Test directory access
            test_photos_dir = test_env.paths.test_photos_dir

            try:
                dir_info = file_service.get_file_info(test_photos_dir)
                TestAssertions.assert_photos_discovered(
                    file_service,
                    test_photos_dir,
                    expected_count=photo_count,
                    tolerance=5,  # Allow some tolerance
                )
                reporter.add_result(
                    "Photo Discovery", True, f"Discovered {photo_count} photos"
                )
            except Exception as e:
                reporter.add_result("Photo Discovery", False, str(e))

            # Test scan estimation
            try:
                estimate = scanner.estimate_scan_size(test_photos_dir, recursive=True)
                expected_files = estimate.get("total_photo_files", 0)

                if expected_files > 0:
                    reporter.add_result(
                        "Scan Estimation",
                        True,
                        f"Estimated {expected_files} files, {estimate.get('total_size_mb', 0):.1f}MB",
                    )
                else:
                    reporter.add_result("Scan Estimation", False, "No files estimated")
            except Exception as e:
                reporter.add_result("Scan Estimation", False, str(e))

            # Test fast scan
            try:
                fast_options = ScanOptions(
                    strategy=ScanStrategy.FAST_METADATA_ONLY,
                    max_files=5,
                    recursive=True,
                )
                fast_result = scanner.scan_directory(test_photos_dir, fast_options)

                TestAssertions.assert_scan_successful(fast_result, min_success_rate=0.8)
                reporter.add_result(
                    "Fast Scan",
                    True,
                    f"Processed {fast_result.successful_files}/{fast_result.total_files} files",
                )
            except Exception as e:
                reporter.add_result("Fast Scan", False, str(e))

            # Test full metadata scan (limited files)
            try:
                full_options = ScanOptions(
                    strategy=ScanStrategy.FULL_METADATA, max_files=3, recursive=True
                )
                full_result = scanner.scan_directory(test_photos_dir, full_options)

                TestAssertions.assert_scan_successful(full_result, min_success_rate=0.8)

                # Check metadata quality
                if full_result.files:
                    sample_file = full_result.files[0]
                    metadata = sample_file.get("metadata", {})
                    TestAssertions.assert_metadata_extracted(
                        metadata, ["file_path", "file_size", "width", "height"]
                    )

                reporter.add_result(
                    "Full Metadata Scan",
                    True,
                    f"Extracted metadata from {len(full_result.files)} files",
                )
            except Exception as e:
                reporter.add_result("Full Metadata Scan", False, str(e))

        # Report results
        success = reporter.print_summary()
        assert (
            success
        ), f"Pipeline test failed with {reporter.get_success_rate():.1f}% success rate"

    def test_pipeline_with_synthetic_photos(self):
        """Test the pipeline using synthetic test photos."""
        reporter = TestReporter()

        with temporary_test_directory() as temp_dir:
            with isolated_test_environment() as test_env:
                # Create synthetic test structure
                builder = TestFileSystemBuilder(temp_dir)
                test_dir = (
                    builder.add_photos("photos", 5).add_nested_structure().build()
                )

                reporter.add_result(
                    "Synthetic Photo Creation",
                    True,
                    f"Created test structure in {test_dir}",
                )

                # Override allowed directories for this test
                service_builder = ServiceTestBuilder(test_env)
                file_service = service_builder.build_file_system_service([test_dir])
                scanner = service_builder.build_directory_scanner(file_service)

                # Test photo discovery
                try:
                    photos = file_service.get_photo_files(test_dir, recursive=True)
                    expected_count = 5 + 3 + 2 + 1  # From nested structure

                    TestAssertions.assert_photos_discovered(
                        file_service,
                        test_dir,
                        expected_count=expected_count,
                        tolerance=1,
                    )
                    reporter.add_result(
                        "Synthetic Photo Discovery", True, f"Found {len(photos)} photos"
                    )
                except Exception as e:
                    reporter.add_result("Synthetic Photo Discovery", False, str(e))

                # Test complete scan
                try:
                    options = ScanOptions(
                        strategy=ScanStrategy.FULL_METADATA, recursive=True
                    )
                    result = scanner.scan_directory(test_dir, options)

                    TestAssertions.assert_scan_successful(
                        result, min_success_rate=1.0
                    )  # Should be 100% for synthetic
                    reporter.add_result(
                        "Synthetic Complete Scan",
                        True,
                        f"Perfect scan: {result.successful_files} files processed",
                    )
                except Exception as e:
                    reporter.add_result("Synthetic Complete Scan", False, str(e))

        success = reporter.print_summary()
        assert success, "Synthetic pipeline test failed"


class TestSecurityValidation:
    """Test security aspects of the photo processing pipeline."""

    def test_path_traversal_protection(self):
        """Test that path traversal attacks are blocked."""
        reporter = TestReporter()

        with isolated_test_environment() as test_env:
            builder = ServiceTestBuilder(test_env)
            file_service = builder.build_file_system_service()

            # Test various path traversal attempts
            dangerous_paths = [
                Path("../../../etc/passwd"),
                Path("..") / ".." / "sensitive_file.txt",
                test_env.paths.test_photos_dir / ".." / ".." / "etc" / "passwd",
            ]

            blocked_count = 0
            for dangerous_path in dangerous_paths:
                try:
                    TestAssertions.assert_security_violation_blocked(
                        file_service.validate_path_access, dangerous_path
                    )
                    blocked_count += 1
                except AssertionError as e:
                    reporter.add_result(
                        f"Path Traversal Block: {dangerous_path.name}", False, str(e)
                    )
                    continue

                reporter.add_result(
                    f"Path Traversal Block: {dangerous_path.name}",
                    True,
                    "Properly blocked",
                )

            overall_success = blocked_count == len(dangerous_paths)
            reporter.add_result(
                "Overall Path Traversal Protection",
                overall_success,
                f"Blocked {blocked_count}/{len(dangerous_paths)} attacks",
            )

        success = reporter.print_summary()
        assert success, "Security validation failed"

    def test_file_type_filtering(self):
        """Test that dangerous file types are filtered."""
        reporter = TestReporter()

        with temporary_test_directory() as temp_dir:
            with isolated_test_environment() as test_env:
                # Create test files including dangerous ones
                test_files = [
                    ("photo.jpg", "fake photo"),
                    ("script.py", "malicious script"),
                    ("document.txt", "text file"),
                    ("executable.exe", "binary"),
                ]

                for filename, content in test_files:
                    (temp_dir / filename).write_text(content)

                builder = ServiceTestBuilder(test_env)
                file_service = builder.build_file_system_service([temp_dir])

                # Test photo discovery (should only find photos)
                photos = file_service.get_photo_files(temp_dir, recursive=False)
                photo_names = [p.path.name for p in photos]

                # Should only contain photo files
                assert "photo.jpg" in photo_names
                assert "script.py" not in photo_names
                assert "executable.exe" not in photo_names

                reporter.add_result(
                    "File Type Filtering",
                    True,
                    f"Correctly filtered to {len(photos)} photo files",
                )

        success = reporter.print_summary()
        assert success, "File type filtering failed"


def run_integration_tests():
    """Run all integration tests and return success status."""
    print("🧪 Running Photo Processing Pipeline Integration Tests")
    print("=" * 60)

    # Test classes
    pipeline_tests = TestPhotoProcessingPipeline()
    security_tests = TestSecurityValidation()

    overall_reporter = TestReporter()

    # Run pipeline tests
    try:
        pipeline_tests.test_pipeline_with_real_photos()
        overall_reporter.add_result("Real Photos Pipeline", True)
    except Exception as e:
        overall_reporter.add_result("Real Photos Pipeline", False, str(e))

    try:
        pipeline_tests.test_pipeline_with_synthetic_photos()
        overall_reporter.add_result("Synthetic Photos Pipeline", True)
    except Exception as e:
        overall_reporter.add_result("Synthetic Photos Pipeline", False, str(e))

    # Run security tests
    try:
        security_tests.test_path_traversal_protection()
        overall_reporter.add_result("Path Traversal Protection", True)
    except Exception as e:
        overall_reporter.add_result("Path Traversal Protection", False, str(e))

    try:
        security_tests.test_file_type_filtering()
        overall_reporter.add_result("File Type Filtering", True)
    except Exception as e:
        overall_reporter.add_result("File Type Filtering", False, str(e))

    print("\n🎯 OVERALL INTEGRATION TEST RESULTS")
    return overall_reporter.print_summary()


if __name__ == "__main__":
    import sys

    success = run_integration_tests()
    sys.exit(0 if success else 1)
