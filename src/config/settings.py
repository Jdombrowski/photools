from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.services.file_system_service import SecurityConstraints


class PhotoDirectorySettings(BaseSettings):
    """Settings for photo directory access and security."""

    # Allowed photo directories (comma-separated in env var)
    allowed_photo_directories_str: str = Field(
        default=str(Path.home() / "Pictures"),
        description="Allowed directories for photo scanning (comma-separated)",
        alias="allowed_photo_directories",
    )

    # Security constraints
    max_file_size_mb: int = Field(
        default=100, description="Maximum file size in MB for photo processing"
    )

    max_directory_depth: int = Field(
        default=5, description="Maximum directory traversal depth"
    )

    follow_symlinks: bool = Field(
        default=False, description="Whether to follow symbolic links"
    )

    skip_hidden_files: bool = Field(
        default=True, description="Whether to skip hidden files (starting with .)"
    )

    skip_hidden_directories: bool = Field(
        default=True, description="Whether to skip hidden directories (starting with .)"
    )

    # Photo file extensions
    photo_extensions: set[str] = Field(
        default_factory=lambda: {
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
        },
        description="Supported photo file extensions",
    )

    # Scanning settings
    enable_recursive_scan: bool = Field(
        default=True, description="Enable recursive directory scanning by default"
    )

    scan_batch_size: int = Field(
        default=50, description="Number of files to process in each batch"
    )

    # Additional security settings
    strict_path_validation: bool = Field(
        default=True, description="Enable strict path validation and security checks"
    )

    log_security_violations: bool = Field(
        default=True, description="Log all security violations for monitoring"
    )

    block_executable_files: bool = Field(
        default=True, description="Block access to executable and script files"
    )

    @property
    def allowed_photo_directories(self) -> list[str]:
        """Get parsed list of allowed photo directories."""
        if isinstance(self.allowed_photo_directories_str, str):
            return [
                d.strip()
                for d in self.allowed_photo_directories_str.split(",")
                if d.strip()
            ]
        return [self.allowed_photo_directories_str]

    @field_validator("photo_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, v):
        """Parse comma-separated extensions from environment variable."""
        if isinstance(v, str):
            extensions = {ext.strip().lower() for ext in v.split(",") if ext.strip()}
            # Ensure extensions start with dot
            return {ext if ext.startswith(".") else f".{ext}" for ext in extensions}
        return v

    def get_validated_directories(self) -> list[str]:
        """Get validated list of directories that exist."""
        valid_dirs = []

        for dir_path in self.allowed_photo_directories:
            path = Path(dir_path).expanduser().resolve()
            if path.exists() and path.is_dir():
                valid_dirs.append(str(path))
            elif path.exists() and not path.is_dir():
                # If the path exists but is not a directory, log a warning
                print(f"Warning: Path is not a directory: {dir_path}")
            else:
                # In development, we may have directories that don't exist yet
                # Include them anyway but log a warning
                print(f"Warning: Directory does not exist: {dir_path}")
                valid_dirs.append(str(path))
        return valid_dirs or [str(Path.home() / "Pictures")]

    def get_security_constraints(self) -> SecurityConstraints:
        return SecurityConstraints(
            allowed_extensions=self.photo_extensions,
            max_file_size_mb=self.max_file_size_mb,
            max_depth=self.max_directory_depth,
            follow_symlinks=self.follow_symlinks,
            skip_hidden_files=self.skip_hidden_files,
            skip_hidden_directories=self.skip_hidden_directories,
        )

    model_config = SettingsConfigDict(
        env_prefix="PHOTO_",
        case_sensitive=False,
        extra="ignore",
        env_parse_none_str="",
        env_parse_enums=False,
    )


class DatabaseSettings(BaseSettings):
    """Database connection settings."""

    database_url: str = Field(
        default="postgresql://photo_user:photo_password@localhost:5432/photo_catalog",
        description="Database connection URL",
    )

    database_pool_size: int = Field(
        default=10, description="Database connection pool size"
    )

    database_max_overflow: int = Field(
        default=20, description="Maximum database connection pool overflow"
    )

    model_config = {
        "env_prefix": "DATABASE_",
        "case_sensitive": False,
        "extra": "ignore",
    }


class CelerySettings(BaseSettings):
    """Celery task queue settings."""

    broker_url: str = Field(
        default="redis://localhost:6379/0", description="Celery broker URL"
    )

    result_backend: str = Field(
        default="redis://localhost:6379/1", description="Celery result backend URL"
    )

    task_serializer: str = Field(default="json", description="Celery task serializer")

    result_serializer: str = Field(
        default="json", description="Celery result serializer"
    )

    timezone: str = Field(default="UTC", description="Celery timezone")

    enable_utc: bool = Field(default=True, description="Enable UTC timezone")

    model_config = {"env_prefix": "CELERY_", "case_sensitive": False, "extra": "ignore"}


class APISettings(BaseSettings):
    """API server settings."""

    title: str = Field(default="Photools API", description="API title")

    description: str = Field(
        default="Media cataloging suite for managing and executing AI model routing within a photo metadata database",
        description="API description",
    )

    version: str = Field(default="0.1.0", description="API version")

    host: str = Field(default="0.0.0.0", description="API host")

    port: int = Field(default=8000, description="API port")

    debug: bool = Field(default=False, description="Enable debug mode")

    reload: bool = Field(default=False, description="Enable auto-reload in development")

    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="Secret key for security operations",
    )

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8000"],
        description="CORS allowed origins",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse comma-separated CORS origins from environment variable."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    model_config = {"env_prefix": "API_", "case_sensitive": False, "extra": "ignore"}


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    log_level: str = Field(default="INFO", description="Logging level")

    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format",
    )

    log_file: str | None = Field(
        default=None, description="Log file path (if None, logs to console)"
    )

    max_log_file_size_mb: int = Field(
        default=100, description="Maximum log file size in MB"
    )

    max_log_files: int = Field(
        default=5, description="Maximum number of log files to keep"
    )

    model_config = {"env_prefix": "LOG_", "case_sensitive": False, "extra": "ignore"}


class Settings(BaseSettings):
    """Main application settings."""

    # Environment
    environment: str = Field(
        default="development", description="Application environment"
    )

    # Component settings
    photos: PhotoDirectorySettings = Field(default_factory=PhotoDirectorySettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    api: APISettings = Field(default_factory=APISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    # Global settings
    project_name: str = Field(default="photools", description="Project name")

    version: str = Field(default="0.1.0", description="Application version")

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        """Validate environment setting."""
        allowed_environments = {"development", "testing", "staging", "production"}
        if v.lower() not in allowed_environments:
            raise ValueError(f"Environment must be one of: {allowed_environments}")
        return v.lower()

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get application settings (singleton pattern)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings (useful for testing)."""
    global _settings
    _settings = None
    return get_settings()


# Convenience functions for commonly used settings
def get_photo_directories() -> list[Path]:
    """Get list of allowed photo directories as Path objects."""
    settings = get_settings()
    return [Path(d) for d in settings.photos.allowed_photo_directories]


def get_photo_extensions() -> set[str]:
    """Get set of allowed photo file extensions."""
    settings = get_settings()
    return settings.photos.photo_extensions


def is_development() -> bool:
    """Check if running in development environment."""
    return get_settings().environment == "development"


def is_production() -> bool:
    """Check if running in production environment."""
    return get_settings().environment == "production"
