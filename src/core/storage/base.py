from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from enum import Enum


class StorageOperationResult(Enum):
    """Result types for storage operations."""
    SUCCESS = "success"
    DUPLICATE = "duplicate"
    ERROR = "error"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"


@dataclass
class StorageResult:
    """Result of a storage operation."""
    result: StorageOperationResult
    storage_path: Optional[str] = None
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    metadata: Optional[Dict] = None
    error_message: Optional[str] = None
    
    @property
    def success(self) -> bool:
        return self.result == StorageOperationResult.SUCCESS
    
    @property
    def is_duplicate(self) -> bool:
        return self.result == StorageOperationResult.DUPLICATE


@dataclass
class StorageConfig:
    """Configuration for storage backends."""
    base_path: Union[str, Path]
    organize_by_date: bool = True
    date_format: str = "%Y/%m/%d"  # Year/Month/Day
    preserve_original_names: bool = False
    use_content_hash: bool = True
    max_file_size_mb: int = 100


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    def __init__(self, config: StorageConfig):
        self.config = config
    
    @abstractmethod
    async def store_file(
        self, 
        file_content: bytes, 
        filename: str, 
        content_type: str,
        metadata: Optional[Dict] = None
    ) -> StorageResult:
        """Store a file and return storage result."""
        pass
    
    @abstractmethod
    async def retrieve_file(self, storage_path: str) -> Optional[bytes]:
        """Retrieve file content by storage path."""
        pass
    
    @abstractmethod
    async def delete_file(self, storage_path: str) -> bool:
        """Delete a file from storage."""
        pass
    
    @abstractmethod
    async def file_exists(self, storage_path: str) -> bool:
        """Check if file exists at storage path."""
        pass
    
    @abstractmethod
    async def get_file_info(self, storage_path: str) -> Optional[Dict]:
        """Get file metadata/info."""
        pass
    
    @abstractmethod
    async def list_files(
        self, 
        path_prefix: str = "", 
        limit: Optional[int] = None
    ) -> List[Dict]:
        """List files with optional path prefix and limit."""
        pass
    
    @abstractmethod
    async def check_duplicate(self, file_hash: str) -> Optional[str]:
        """Check if file with hash already exists, return storage path if found."""
        pass
    
    # Convenience methods
    def generate_storage_path(
        self, 
        filename: str, 
        file_hash: str, 
        date_taken: Optional[datetime] = None
    ) -> str:
        """Generate storage path based on configuration."""
        
        # Use date_taken if available, otherwise current date
        target_date = date_taken or datetime.utcnow()
        
        # Get file extension
        file_ext = Path(filename).suffix.lower()
        
        if self.config.organize_by_date:
            date_path = target_date.strftime(self.config.date_format)
            
            if self.config.use_content_hash:
                # Use hash as filename for deduplication
                final_filename = f"{file_hash}{file_ext}"
            elif self.config.preserve_original_names:
                # Keep original name but add timestamp if needed
                stem = Path(filename).stem
                timestamp = target_date.strftime("_%H%M%S")
                final_filename = f"{stem}{timestamp}{file_ext}"
            else:
                # Generate intelligent name based on date
                final_filename = f"{target_date.strftime('%Y%m%d_%H%M%S')}{file_ext}"
            
            return str(Path(date_path) / final_filename)
        else:
            # Flat structure
            if self.config.use_content_hash:
                return f"{file_hash}{file_ext}"
            else:
                return filename
    
    def validate_file(self, file_content: bytes, filename: str, content_type: str) -> Optional[str]:
        """Validate file before storage. Returns error message if invalid."""
        
        # Check file size
        file_size_mb = len(file_content) / (1024 * 1024)
        if file_size_mb > self.config.max_file_size_mb:
            return f"File too large: {file_size_mb:.1f}MB (max: {self.config.max_file_size_mb}MB)"
        
        # Check file extension
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.raw', '.cr2', '.nef', '.arw'}
        file_ext = Path(filename).suffix.lower()
        if file_ext not in allowed_extensions:
            return f"Unsupported file type: {file_ext}"
        
        # Check content type
        allowed_content_types = {
            'image/jpeg', 'image/png', 'image/tiff', 
            'image/x-canon-cr2', 'image/x-nikon-nef', 'image/x-sony-arw'
        }
        if content_type not in allowed_content_types and not content_type.startswith('image/'):
            return f"Unsupported content type: {content_type}"
        
        return None  # No errors