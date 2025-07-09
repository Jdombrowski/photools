import logging
import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AccessLevel(Enum):
    """Define different access levels for file system operations."""

    READ_ONLY = "read_only"
    METADATA_ONLY = "metadata_only"
    NO_ACCESS = "no_access"


@dataclass
class SecurityConstraints:
    """Security constraints for file system access."""

    max_file_size_mb: int = 500  # Maximum file size in MB
    allowed_extensions: set[str] | None = None
    max_depth: int = 10  # Maximum directory traversal depth
    follow_symlinks: bool = False
    skip_hidden_files: bool = True
    skip_hidden_directories: bool = True
    max_path_length: int = 4096  # Maximum path length
    allowed_drives: set[str] | None = None  # Windows: allowed drive letters
    block_executable_extensions: bool = True  # Block potentially dangerous files
    strict_extension_validation: bool = True  # Only allow explicitly listed extensions
    enable_symlink_escape_detection: bool = True  # Check for symlink escapes
    log_security_violations: bool = True  # Log all security violations

    def __post_init__(self):
        if self.allowed_extensions is None:
            self.allowed_extensions = {
                ".jpg",
                ".jpeg",
                ".png",
                ".tiff",
                ".tif",
                ".bmp",
                ".webp",
                ".heic",
                ".heif",
                ".raw",
                ".cr2",
                ".nef",
                ".arw",
                ".dng",
                ".orf",
                ".raf",
                ".rw2",
                ".pef",
                ".srw",
                ".x3f",
                ".3fr",
                ".fff",
                ".iiq",
                ".k25",
                ".kdc",
                ".mef",
                ".mos",
                ".mrw",
                ".nrw",
                ".ptx",
                ".r3d",
                ".rwl",
                ".sr2",
                ".srf",
            }

        if self.allowed_drives is None:
            # Default allowed Windows drives (only if on Windows)
            self.allowed_drives = {"c:", "d:", "e:", "f:", "g:", "h:"}


@dataclass
class FileSystemEntry:
    """Represents a file system entry with security information."""

    path: Path
    is_directory: bool
    size: int
    access_level: AccessLevel
    permissions: str
    last_modified: float
    is_symlink: bool = False
    error: str | None = None


class FileSystemSecurityError(Exception):
    """Custom exception for file system security violations."""

    pass


class SecureFileSystemService:
    """Secure file system service with readonly access and security constraints.

    This service provides controlled access to the file system with:
    - Path traversal protection
    - Directory allowlisting
    - File size and type restrictions
    - Read-only access enforcement
    - Security audit logging
    """

    def __init__(
        self,
        allowed_directories: list[Path],
        constraints: SecurityConstraints | None = None,
    ):
        """Initialize secure file system service.

        Args:
            allowed_directories: List of allowed root directories
            constraints: Security constraints configuration

        """
        self.allowed_directories = [Path(d).resolve() for d in allowed_directories]
        self.constraints = constraints or SecurityConstraints()

        # Validate allowed directories exist and are accessible
        self._validate_allowed_directories()

        # Log security configuration
        logger.info(
            f"SecureFileSystemService initialized with {len(self.allowed_directories)} allowed directories"
        )
        for i, directory in enumerate(self.allowed_directories):
            logger.info(f"  Allowed directory {i+1}: {directory}")
        logger.info(
            f"Security constraints: max_file_size={self.constraints.max_file_size_mb}MB, max_depth={self.constraints.max_depth}, follow_symlinks={self.constraints.follow_symlinks}"
        )

    def _validate_allowed_directories(self) -> None:
        """Validate that allowed directories exist and are accessible."""
        for directory in self.allowed_directories:
            if not directory.exists():
                raise FileSystemSecurityError(
                    f"Allowed directory does not exist: {directory}"
                )
            if not directory.is_dir():
                raise FileSystemSecurityError(
                    f"Allowed path is not a directory: {directory}"
                )
            if not os.access(directory, os.R_OK):
                raise FileSystemSecurityError(
                    f"No read access to directory: {directory}"
                )

    def _normalize_path(self, path: Path) -> Path:
        """Normalize and resolve path with extensive security validation.

        This method prevents:
        - Path traversal attacks (../, .\\, etc.)
        - Null byte injection
        - Invalid characters
        - Excessively long paths
        - Special device files
        """
        try:
            # Convert to string for validation
            path_str = str(path)

            # Check for null bytes (security vulnerability)
            if "\x00" in path_str:
                raise FileSystemSecurityError(f"Null byte detected in path: {path}")

            # Check for excessively long paths
            if len(path_str) > self.constraints.max_path_length:
                raise FileSystemSecurityError(
                    f"Path too long: {len(path_str)} characters (max: {self.constraints.max_path_length})"
                )

            # Check for suspicious patterns
            suspicious_patterns = [
                "..\\",  # Windows path traversal
                "../",  # Unix path traversal
                "..\\\\",  # Double backslash
                "%2e%2e",  # URL encoded ..
                "%2f",  # URL encoded /
                "%5c",  # URL encoded \\
                "\\\\?\\",  # UNC path prefix
                "\\\\.",  # Device namespace
            ]

            path_lower = path_str.lower()
            for pattern in suspicious_patterns:
                if pattern in path_lower:
                    if self.constraints.log_security_violations:
                        logger.warning(
                            f"SECURITY ALERT: Suspicious path pattern detected: {pattern} in {path}"
                        )
                    raise FileSystemSecurityError(
                        f"Suspicious path pattern detected: {pattern} in {path}"
                    )

            # Resolve the path (this handles .. and . components)
            resolved_path = Path(path).resolve(strict=False)

            # Additional check: ensure resolved path doesn't contain .. components
            # This catches cases where resolve() might not catch everything
            resolved_str = str(resolved_path)
            if "/.." in resolved_str or "\\..\\" in resolved_str:
                raise FileSystemSecurityError(
                    f"Path traversal detected after resolution: {resolved_path}"
                )

            return resolved_path

        except (OSError, ValueError) as e:
            raise FileSystemSecurityError(f"Invalid path: {path}, error: {e}")

    def _is_path_allowed(self, path: Path) -> bool:
        """Check if path is within allowed directories with strict validation.

        Uses multiple validation methods to prevent bypass attempts.
        """
        normalized_path = self._normalize_path(path)

        # Convert to absolute path for comparison
        try:
            abs_path = normalized_path.resolve()
        except (OSError, RuntimeError) as e:
            logger.warning(f"Could not resolve absolute path for {path}: {e}")
            return False

        # Check against each allowed directory
        for allowed_dir in self.allowed_directories:
            try:
                # Method 1: Use relative_to() which is the most reliable
                abs_path.relative_to(allowed_dir)

                # Method 2: Double-check with string comparison
                abs_path_str = str(abs_path)
                allowed_str = str(allowed_dir)

                # Ensure path starts with allowed directory + separator
                # This prevents /allowed/dir being bypassed by /allowed/directory
                if abs_path_str == allowed_str or abs_path_str.startswith(
                    allowed_str + os.sep
                ):
                    # Method 3: Verify no symlink escaping by checking all parent directories
                    if self._verify_no_symlink_escape(abs_path, allowed_dir):
                        return True

            except ValueError:
                # relative_to() raises ValueError if path is not relative
                continue

        return False

    def _verify_no_symlink_escape(self, target_path: Path, allowed_root: Path) -> bool:
        """Verify that no symlinks in the path escape the allowed root directory.

        This prevents attacks where symlinks are used to escape the jail.
        """
        try:
            # Check each component of the path for symlinks that escape
            current_path = allowed_root

            # Get relative path components
            relative_path = target_path.relative_to(allowed_root)

            # Check each component in the path
            for component in relative_path.parts:
                current_path = current_path / component

                # If this component is a symlink, verify it doesn't escape
                if current_path.is_symlink():
                    # Resolve the symlink target
                    try:
                        symlink_target = current_path.resolve()

                        # Check if symlink target is within allowed root
                        try:
                            symlink_target.relative_to(allowed_root)
                        except ValueError:
                            logger.warning(
                                f"Symlink escape detected: {current_path} -> {symlink_target} (outside {allowed_root})"
                            )
                            return False

                    except (OSError, RuntimeError) as e:
                        logger.warning(f"Could not resolve symlink {current_path}: {e}")
                        return False

            return True

        except (ValueError, OSError) as e:
            logger.warning(f"Error verifying symlink escape for {target_path}: {e}")
            return False

    def _check_system_directory_access(self, path: Path) -> None:
        """Prevent access to system-critical directories.

        Raises FileSystemSecurityError if path accesses dangerous system directories.
        """
        path_str = str(path).lower()

        # System directories that should never be accessible
        forbidden_patterns = [
            "/etc/",
            "/boot/",
            "/sys/",
            "/proc/",
            "/dev/",
            "/root/",
            "/var/log/",
            "/var/spool/",
            "/usr/bin/",
            "/usr/sbin/",
            "/sbin/",
            "/bin/",
            "c:\\windows\\",
            "c:\\program files\\",
            "c:\\users\\administrator\\",
            "c:\\users\\default\\",
            "\\windows\\",
            "\\program files\\",
            "\\system32\\",
            "\\syswow64\\",
        ]

        for pattern in forbidden_patterns:
            if pattern in path_str:
                raise FileSystemSecurityError(
                    f"SECURITY VIOLATION: Access to system directory denied: {path}"
                )

        # Additional check for Windows drive root access
        if os.name == "nt" and len(path.parts) > 0:
            root_part = path.parts[0].lower()
            if root_part.endswith(":") or root_part.endswith(":\\\\"):
                # Only allow specific drive letters if configured
                allowed_drives = getattr(
                    self.constraints, "allowed_drives", {"c:", "d:", "e:", "f:"}
                )
                if root_part not in [d.lower() for d in allowed_drives]:
                    raise FileSystemSecurityError(
                        f"SECURITY VIOLATION: Drive access not allowed: {root_part}"
                    )

    def _check_dangerous_file_types(self, path: Path) -> None:
        """Prevent access to potentially dangerous file types.

        Raises FileSystemSecurityError for dangerous file extensions.
        """
        if not path.is_file() and not path.exists():
            return  # Only check existing files

        dangerous_extensions = {
            # Executable files
            ".exe",
            ".bat",
            ".cmd",
            ".com",
            ".scr",
            ".pif",
            ".vbs",
            ".vbe",
            ".js",
            ".jse",
            ".wsf",
            ".wsh",
            ".msi",
            ".msp",
            ".dll",
            ".sys",
            ".drv",
            # Script files
            ".sh",
            ".bash",
            ".zsh",
            ".csh",
            ".fish",
            ".pl",
            ".py",
            ".rb",
            ".lua",
            ".ps1",
            # Archive files that might contain executables
            ".zip",
            ".rar",
            ".7z",
            ".tar",
            ".gz",
            ".bz2",
            # System files
            ".ini",
            ".cfg",
            ".conf",
            ".config",
            ".plist",
            ".reg",
            ".key",
            ".crt",
            ".pem",
            ".p12",
            # Database files
            ".db",
            ".sqlite",
            ".mdb",
            ".accdb",
            # Log files (might contain sensitive info)
            ".log",
            ".tmp",
            ".temp",
            ".swp",
            ".bak",
        }

        file_extension = path.suffix.lower()
        if file_extension in dangerous_extensions:
            # Allow only if explicitly in allowed extensions
            if file_extension not in self.constraints.allowed_extensions:
                raise FileSystemSecurityError(
                    f"SECURITY VIOLATION: Dangerous file type not allowed: {file_extension}"
                )

    def _check_file_constraints(self, file_path: Path) -> AccessLevel:
        """Check if file meets security constraints."""
        try:
            # Check file size
            file_size = file_path.stat().st_size
            max_size_bytes = self.constraints.max_file_size_mb * 1024 * 1024

            if file_size > max_size_bytes:
                logger.warning(
                    f"File exceeds size limit: {file_path} ({file_size} bytes)"
                )
                return AccessLevel.NO_ACCESS

            # Check file extension
            if file_path.suffix.lower() not in self.constraints.allowed_extensions:
                logger.debug(f"File extension not allowed: {file_path}")
                return AccessLevel.NO_ACCESS

            # Check if file is readable
            if not os.access(file_path, os.R_OK):
                logger.warning(f"No read access to file: {file_path}")
                return AccessLevel.NO_ACCESS

            return AccessLevel.READ_ONLY

        except (OSError, PermissionError) as e:
            logger.error(f"Error checking file constraints for {file_path}: {e}")
            return AccessLevel.NO_ACCESS

    def _get_file_permissions_string(self, file_path: Path) -> str:
        """Get human-readable file permissions string."""
        try:
            file_stat = file_path.stat()
            return stat.filemode(file_stat.st_mode)
        except (OSError, PermissionError):
            return "unknown"

    def validate_path_access(self, path: Path) -> bool:
        """Validate that a path can be safely accessed with comprehensive security checks.

        Args:
            path: Path to validate

        Returns:
            True if path is safe to access, False otherwise

        Raises:
            FileSystemSecurityError: If path represents a security violation

        """
        # First normalize and basic security check
        normalized_path = self._normalize_path(path)

        # Explicit check: Path must be within allowed directories
        if not self._is_path_allowed(path):
            raise FileSystemSecurityError(
                f"SECURITY VIOLATION: Path not in allowed directories: {path}"
            )

        # Explicit check: Prevent access to system-critical directories
        self._check_system_directory_access(normalized_path)

        # Explicit check: Prevent access to dangerous file types
        self._check_dangerous_file_types(normalized_path)

        # Check for symlink policy
        if normalized_path.is_symlink() and not self.constraints.follow_symlinks:
            raise FileSystemSecurityError(
                f"SECURITY VIOLATION: Symlinks not allowed: {path}"
            )

        # Check hidden file/directory policy
        if normalized_path.name.startswith("."):
            if normalized_path.is_dir() and self.constraints.skip_hidden_directories:
                raise FileSystemSecurityError(
                    f"SECURITY VIOLATION: Hidden directories not allowed: {path}"
                )
            elif normalized_path.is_file() and self.constraints.skip_hidden_files:
                raise FileSystemSecurityError(
                    f"SECURITY VIOLATION: Hidden files not allowed: {path}"
                )

        # Final validation: Double-check the resolved path is still within bounds
        try:
            final_resolved = normalized_path.resolve(strict=False)
            if not self._is_path_allowed(final_resolved):
                raise FileSystemSecurityError(
                    f"SECURITY VIOLATION: Resolved path escapes allowed directories: {path} -> {final_resolved}"
                )
        except (OSError, RuntimeError) as e:
            raise FileSystemSecurityError(
                f"SECURITY VIOLATION: Cannot resolve path safely: {path}, error: {e}"
            )

        return True

    def get_file_info(self, file_path: Path) -> FileSystemEntry:
        """Get secure file information for a single file.

        Args:
            file_path: Path to the file

        Returns:
            FileSystemEntry with file information and access level

        """
        try:
            self.validate_path_access(file_path)
            normalized_path = self._normalize_path(file_path)

            if not normalized_path.exists():
                return FileSystemEntry(
                    path=normalized_path,
                    is_directory=False,
                    size=0,
                    access_level=AccessLevel.NO_ACCESS,
                    permissions="",
                    last_modified=0,
                    error="File not found",
                )

            file_stat = normalized_path.stat()
            is_directory = normalized_path.is_dir()

            # Determine access level
            if is_directory:
                access_level = AccessLevel.READ_ONLY
            else:
                access_level = self._check_file_constraints(normalized_path)

            return FileSystemEntry(
                path=normalized_path,
                is_directory=is_directory,
                size=file_stat.st_size,
                access_level=access_level,
                permissions=self._get_file_permissions_string(normalized_path),
                last_modified=file_stat.st_mtime,
                is_symlink=normalized_path.is_symlink(),
            )

        except FileSystemSecurityError as e:
            logger.warning(f"Security error accessing {file_path}: {e}")
            return FileSystemEntry(
                path=file_path,
                is_directory=False,
                size=0,
                access_level=AccessLevel.NO_ACCESS,
                permissions="",
                last_modified=0,
                error=str(e),
            )
        except Exception as e:
            logger.error(f"Unexpected error accessing {file_path}: {e}")
            return FileSystemEntry(
                path=file_path,
                is_directory=False,
                size=0,
                access_level=AccessLevel.NO_ACCESS,
                permissions="",
                last_modified=0,
                error=f"Access error: {e}",
            )

    def list_directory(
        self,
        directory_path: Path,
        recursive: bool = False,
        max_depth: int | None = None,
    ) -> list[FileSystemEntry]:
        """Safely list directory contents with security constraints.

        Args:
            directory_path: Directory to list
            recursive: Whether to list recursively
            max_depth: Maximum recursion depth (overrides constraints if specified)

        Returns:
            List of FileSystemEntry objects for accessible files/directories

        """
        try:
            self.validate_path_access(directory_path)
            normalized_path = self._normalize_path(directory_path)

            if not normalized_path.is_dir():
                raise FileSystemSecurityError(
                    f"Path is not a directory: {directory_path}"
                )

            entries = []
            max_depth = max_depth or self.constraints.max_depth

            self._list_directory_recursive(
                directory=normalized_path,
                entries=entries,
                current_depth=0,
                max_depth=max_depth if recursive else 0,
            )

            logger.info(f"Listed {len(entries)} entries from {directory_path}")
            return entries

        except FileSystemSecurityError as e:
            logger.error(f"Security error listing directory {directory_path}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing directory {directory_path}: {e}")
            return []

    def _list_directory_recursive(
        self,
        directory: Path,
        entries: list[FileSystemEntry],
        current_depth: int,
        max_depth: int,
    ) -> None:
        """Recursively list directory contents with depth control."""
        try:
            for item in directory.iterdir():
                # Skip hidden files/directories if configured
                if item.name.startswith("."):
                    if (item.is_dir() and self.constraints.skip_hidden_directories) or (
                        item.is_file() and self.constraints.skip_hidden_files
                    ):
                        continue

                # Skip symlinks if not allowed
                if item.is_symlink() and not self.constraints.follow_symlinks:
                    continue

                # Get file info
                file_info = self.get_file_info(item)
                if file_info.access_level != AccessLevel.NO_ACCESS:
                    entries.append(file_info)

                # Recurse into directories if within depth limit
                if (
                    item.is_dir()
                    and current_depth < max_depth
                    and file_info.access_level != AccessLevel.NO_ACCESS
                ):
                    self._list_directory_recursive(
                        directory=item,
                        entries=entries,
                        current_depth=current_depth + 1,
                        max_depth=max_depth,
                    )

        except PermissionError as e:
            logger.warning(f"Permission denied accessing directory {directory}: {e}")
        except Exception as e:
            logger.error(f"Error listing directory {directory}: {e}")

    def get_photo_files(
        self, directory_path: Path, recursive: bool = True
    ) -> list[FileSystemEntry]:
        """Get list of photo files from directory with security filtering.

        Args:
            directory_path: Directory to scan for photos
            recursive: Whether to scan recursively

        Returns:
            List of FileSystemEntry objects for accessible photo files

        """
        all_entries = self.list_directory(directory_path, recursive=recursive)

        # Filter for photo files with read access
        photo_files = [
            entry
            for entry in all_entries
            if (
                not entry.is_directory
                and entry.access_level == AccessLevel.READ_ONLY
                and entry.path.suffix.lower() in self.constraints.allowed_extensions
            )
        ]

        logger.info(
            f"Found {len(photo_files)} accessible photo files in {directory_path}"
        )
        return photo_files

    def get_directory_stats(self, directory_path: Path) -> dict[str, Any]:
        """Get statistics about a directory and its contents.

        Args:
            directory_path: Directory to analyze

        Returns:
            Dictionary with directory statistics

        """
        try:
            photo_files = self.get_photo_files(directory_path, recursive=True)

            total_size = sum(entry.size for entry in photo_files)
            extensions = {}

            for entry in photo_files:
                ext = entry.path.suffix.lower()
                extensions[ext] = extensions.get(ext, 0) + 1

            return {
                "directory": str(directory_path),
                "total_files": len(photo_files),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_extensions": extensions,
                "largest_file": (
                    max(photo_files, key=lambda x: x.size) if photo_files else None
                ),
                "analyzed_at": logger.name,  # Using logger name as timestamp placeholder
            }

        except Exception as e:
            logger.error(f"Error getting directory stats for {directory_path}: {e}")
            return {"directory": str(directory_path), "error": str(e)}

    @staticmethod
    def create_readonly_photo_service(
        allowed_directories: list[Path],
    ) -> "SecureFileSystemService":
        """Create a SecureFileSystemService with the most restrictive security settings
        for readonly photo access.

        Args:
            allowed_directories: List of directories to allow access to

        Returns:
            SecureFileSystemService configured with maximum security constraints

        """
        # Most restrictive security constraints
        constraints = SecurityConstraints(
            max_file_size_mb=100,  # Smaller limit for photos
            max_depth=5,  # Limit directory traversal depth
            follow_symlinks=False,  # Never follow symlinks
            skip_hidden_files=True,
            skip_hidden_directories=True,
            max_path_length=1024,  # Shorter path limit
            block_executable_extensions=True,
            strict_extension_validation=True,
            enable_symlink_escape_detection=True,
            log_security_violations=True,
            # Only common photo extensions
            allowed_extensions={
                ".jpg",
                ".jpeg",
                ".png",
                ".tiff",
                ".tif",
                ".bmp",
                ".webp",
                ".heic",
                ".heif",
            },
        )

        service = SecureFileSystemService(
            allowed_directories=allowed_directories, constraints=constraints
        )

        logger.info("Created read-only photo service with maximum security constraints")
        return service
