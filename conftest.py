"""Global pytest configuration and custom output formatting."""

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logreport(report):
    """Hook to customize test result output - format with newlines and grey paths."""
    if hasattr(report, "nodeid") and report.nodeid and "::" in report.nodeid:
        parts = report.nodeid.split("::")
        if len(parts) >= 2:
            file_path = parts[0]
            remaining_parts = parts[1:]

            # Grey out the file path
            grey_file_path = f"\033[90m{file_path}\033[0m"

            # Format with newlines and indentation
            if len(remaining_parts) == 1:
                # Just method name
                report.nodeid = f"{grey_file_path}::\n    {remaining_parts[0]}"
            elif len(remaining_parts) >= 2:
                # Class and method
                class_part = remaining_parts[0]
                method_part = "::".join(remaining_parts[1:])
                report.nodeid = (
                    f"{grey_file_path}::\n    {class_part}::\n        {method_part}"
                )


# Removed the makereport hook as it was interfering with error messages


@pytest.hookimpl(hookwrapper=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Hook to grey out file paths in the summary section."""
    yield

    # Modify the summary lines that were already written
    if hasattr(terminalreporter, "_tw"):
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
