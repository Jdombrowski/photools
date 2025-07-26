"""Service factory for centralized dependency injection and service management."""

from functools import lru_cache

from src.config.settings import get_settings
from src.core.services.directory_scanner import SecureDirectoryScanner
from src.core.services.file_system_service import SecureFileSystemService
from src.core.services.photo_import_service import PhotoImportService
from src.core.services.photo_upload_service import PhotoUploadService
from src.core.storage.local import LocalStorageBackend


class ServiceFactory:
    """Factory for creating and managing service instances with proper dependency injection."""

    def __init__(self):
        self.settings = get_settings()
        self._instances = {}

    @lru_cache(maxsize=1)
    def get_file_system_service(self) -> SecureFileSystemService:
        """Get or create file system service instance."""
        if "file_system_service" not in self._instances:
            self._instances["file_system_service"] = SecureFileSystemService(
                allowed_directories=self.settings.photos.get_validated_directories(),
                constraints=self.settings.photos.get_security_constraints(),
            )
        return self._instances["file_system_service"]

    @lru_cache(maxsize=1)
    def get_directory_scanner(self) -> SecureDirectoryScanner:
        """Get or create directory scanner instance."""
        if "directory_scanner" not in self._instances:
            self._instances["directory_scanner"] = SecureDirectoryScanner(
                file_system_service=self.get_file_system_service()
            )
        return self._instances["directory_scanner"]

    @lru_cache(maxsize=1)
    def get_storage_backend(self) -> LocalStorageBackend:
        """Get or create storage backend instance."""
        if "storage_backend" not in self._instances:
            storage_config = self.settings.photos.get_storage_config()
            self._instances["storage_backend"] = LocalStorageBackend(
                config=storage_config
            )
        return self._instances["storage_backend"]

    @lru_cache(maxsize=1)
    def get_photo_upload_service(self) -> PhotoUploadService:
        """Get or create photo upload service instance."""
        if "photo_upload_service" not in self._instances:
            self._instances["photo_upload_service"] = PhotoUploadService(
                storage_backend=self.get_storage_backend()
            )
        return self._instances["photo_upload_service"]

    @lru_cache(maxsize=1)
    def get_photo_import_service(self) -> PhotoImportService:
        """Get or create photo import service instance."""
        if "photo_import_service" not in self._instances:
            self._instances["photo_import_service"] = PhotoImportService(
                directory_scanner=self.get_directory_scanner(),
                photo_upload_service=self.get_photo_upload_service(),
                storage_backend=self.get_storage_backend(),
            )
        return self._instances["photo_import_service"]

    def clear_cache(self):
        """Clear all cached instances (useful for testing)."""
        self._instances.clear()
        # Clear lru_cache for all methods
        self.get_file_system_service.cache_clear()
        self.get_directory_scanner.cache_clear()
        self.get_storage_backend.cache_clear()
        self.get_photo_upload_service.cache_clear()
        self.get_photo_import_service.cache_clear()


# Global factory instance
_service_factory: ServiceFactory | None = None


def get_service_factory() -> ServiceFactory:
    """Get the global service factory instance."""
    global _service_factory
    if _service_factory is None:
        _service_factory = ServiceFactory()
    return _service_factory


def reset_service_factory():
    """Reset the global service factory (useful for testing)."""
    global _service_factory
    if _service_factory:
        _service_factory.clear_cache()
    _service_factory = None
