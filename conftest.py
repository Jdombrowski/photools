"""
Global pytest configuration and custom output formatting.
"""

import pytest
import re


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logreport(report):
    """Hook to customize test result output - grey out file paths."""
    if hasattr(report, 'nodeid') and report.nodeid:
        # Apply grey color to file paths in nodeid (everything before ::)
        if "::" in report.nodeid:
            parts = report.nodeid.split("::", 1)
            if len(parts) == 2:
                file_path, test_path = parts
                # Grey out the file path
                grey_file_path = f"\033[90m{file_path}\033[0m"
                report.nodeid = f"{grey_file_path}::{test_path}"


@pytest.hookimpl(hookwrapper=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Hook to grey out file paths in the summary section."""
    outcome = yield
    
    # Modify the summary lines that were already written
    if hasattr(terminalreporter, '_tw'):
        # This runs after the summary is written, so we can't easily modify it
        # The nodeid modification above should handle most cases
        pass


def pytest_collection_modifyitems(config, items):
    """Modify test items during collection - add custom markers."""
    for item in items:
        # Add markers based on file path
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)