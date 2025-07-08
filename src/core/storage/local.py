import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import aiofiles

from .base import StorageBackend, StorageConfig, StorageOperationResult, StorageResult


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend - offline first implementation."""

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.base_path = Path(config.base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Create hash index directory for duplicate detection
        self.hash_index_path = self.base_path / ".photools" / "hash_index"
        self.hash_index_path.mkdir(parents=True, exist_ok=True)

    async def store_file(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        metadata: Optional[Dict] = None,
    ) -> StorageResult:
        """Store file to local filesystem."""

        # Validate file
        validation_error = self.validate_file(file_content, filename, content_type)
        if validation_error:
            return StorageResult(
                result=StorageOperationResult.ERROR, error_message=validation_error
            )

        # Calculate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()

        # Check for duplicates
        existing_path = await self.check_duplicate(file_hash)
        if existing_path:
            return StorageResult(
                result=StorageOperationResult.DUPLICATE,
                storage_path=existing_path,
                file_hash=file_hash,
                file_size=len(file_content),
            )

        try:
            # Extract date from metadata if available
            date_taken = None
            if metadata and metadata.get("date_taken"):
                date_taken = metadata["date_taken"]

            # Generate storage path
            relative_path = self.generate_storage_path(filename, file_hash, date_taken)
            full_path = self.base_path / relative_path

            # Create directory if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            print(f"DEBUG: Writing file to {full_path}")
            async with aiofiles.open(full_path, "wb") as f:
                await f.write(file_content)
            print(f"DEBUG: File written successfully, size: {len(file_content)}")

            # Create hash index entry for duplicate detection
            await self._create_hash_index(file_hash, relative_path)
            print(f"DEBUG: Hash index created for {file_hash}")

            return StorageResult(
                result=StorageOperationResult.SUCCESS,
                storage_path=str(relative_path),
                file_hash=file_hash,
                file_size=len(file_content),
                metadata={"full_path": str(full_path)},
            )

        except PermissionError:
            return StorageResult(
                result=StorageOperationResult.PERMISSION_DENIED,
                error_message=f"Permission denied writing to {self.base_path}",
            )
        except Exception as e:
            return StorageResult(
                result=StorageOperationResult.ERROR,
                error_message=f"Storage error: {str(e)}",
            )

    async def retrieve_file(self, storage_path: str) -> Optional[bytes]:
        """Retrieve file content from local storage."""
        full_path = self.base_path / storage_path

        try:
            if not full_path.exists():
                return None

            async with aiofiles.open(full_path, "rb") as f:
                return await f.read()
        except Exception:
            return None

    async def delete_file(self, storage_path: str) -> bool:
        """Delete file from local storage."""
        full_path = self.base_path / storage_path

        try:
            if full_path.exists():
                full_path.unlink()

                # Remove from hash index
                await self._remove_hash_index(storage_path)
                return True
            return False
        except Exception:
            return False

    async def file_exists(self, storage_path: str) -> bool:
        """Check if file exists in local storage."""
        full_path = self.base_path / storage_path
        return full_path.exists()

    async def get_file_info(self, storage_path: str) -> Optional[Dict]:
        """Get file metadata from local storage."""
        full_path = self.base_path / storage_path

        try:
            if not full_path.exists():
                return None

            stat = full_path.stat()
            return {
                "storage_path": storage_path,
                "full_path": str(full_path),
                "file_size": stat.st_size,
                "created_time": datetime.fromtimestamp(stat.st_ctime),
                "modified_time": datetime.fromtimestamp(stat.st_mtime),
                "is_file": full_path.is_file(),
            }
        except Exception:
            return None

    async def list_files(
        self, path_prefix: str = "", limit: Optional[int] = None
    ) -> List[Dict]:
        """List files in local storage with optional prefix and limit."""

        search_path = self.base_path / path_prefix if path_prefix else self.base_path
        files = []

        try:
            if not search_path.exists():
                return []

            # Use rglob for recursive search
            pattern = "**/*" if search_path.is_dir() else str(search_path.name)

            count = 0
            for file_path in search_path.rglob(pattern):
                if file_path.is_file() and not file_path.name.startswith("."):
                    relative_path = file_path.relative_to(self.base_path)

                    stat = file_path.stat()
                    files.append(
                        {
                            "storage_path": str(relative_path),
                            "filename": file_path.name,
                            "file_size": stat.st_size,
                            "modified_time": datetime.fromtimestamp(stat.st_mtime),
                        }
                    )

                    count += 1
                    if limit and count >= limit:
                        break

            return files
        except Exception:
            return []

    async def check_duplicate(self, file_hash: str) -> Optional[str]:
        """Check if file with hash exists in local storage."""
        hash_file = self.hash_index_path / f"{file_hash}.txt"

        try:
            if hash_file.exists():
                async with aiofiles.open(hash_file, "r") as f:
                    storage_path = (await f.read()).strip()

                # Verify the file still exists
                if await self.file_exists(storage_path):
                    return storage_path
                else:
                    # Clean up stale hash index
                    hash_file.unlink()
                    return None

            return None
        except Exception:
            return None

    async def _create_hash_index(self, file_hash: str, storage_path: str):
        """Create hash index entry for duplicate detection."""
        hash_file = self.hash_index_path / f"{file_hash}.txt"

        try:
            async with aiofiles.open(hash_file, "w") as f:
                await f.write(storage_path)
        except Exception:
            pass  # Non-critical operation

    async def _remove_hash_index(self, storage_path: str):
        """Remove hash index entry when file is deleted."""
        try:
            # Find hash file that contains this storage path
            for hash_file in self.hash_index_path.glob("*.txt"):
                try:
                    async with aiofiles.open(hash_file, "r") as f:
                        content = (await f.read()).strip()

                    if content == storage_path:
                        hash_file.unlink()
                        break
                except Exception:
                    continue
        except Exception:
            pass  # Non-critical operation

    def get_storage_stats(self) -> Dict:
        """Get storage backend statistics."""
        try:
            total_size = 0
            file_count = 0

            for file_path in self.base_path.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith("."):
                    total_size += file_path.stat().st_size
                    file_count += 1

            return {
                "backend_type": "local",
                "base_path": str(self.base_path),
                "total_files": file_count,
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "available_space_bytes": shutil.disk_usage(self.base_path).free,
            }
        except Exception as e:
            return {"backend_type": "local", "error": str(e)}
