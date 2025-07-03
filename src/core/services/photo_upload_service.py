import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.services.photo_processor import PhotoProcessor
from src.core.storage import StorageBackend, StorageConfig, LocalStorageBackend
from src.infrastructure.database.models import Photo, PhotoMetadata
from src.config.settings import get_settings


class PhotoUploadService:
    """Service for handling photo uploads with abstracted storage and database persistence."""

    def __init__(self, storage_backend: Optional[StorageBackend] = None):
        self.settings = get_settings()
        self.photo_processor = PhotoProcessor()
        
        # Use provided storage backend or create default local storage
        if storage_backend:
            self.storage = storage_backend
        else:
            # Use first allowed directory as base path for uploads
            base_path = Path.home() / "Pictures" / "photools_uploads"
            if hasattr(self.settings, 'photos') and self.settings.photos.allowed_photo_directories:
                base_path = Path(self.settings.photos.allowed_photo_directories[0]) / "uploads"
            
            storage_config = StorageConfig(
                base_path=base_path,
                organize_by_date=True,
                use_content_hash=True,
                max_file_size_mb=getattr(self.settings.photos, 'max_file_size_mb', 100)
            )
            self.storage = LocalStorageBackend(storage_config)

    async def process_upload(
    self, 
        file_content: bytes, 
        filename: str, 
        content_type: str,
        db_session: AsyncSession
    ) -> Dict:
        """Process a single photo upload and store in database."""
        
        # Calculate file hash for duplicate detection
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        # Check if photo already exists in database
        existing_photo = await self._check_existing_photo(db_session, file_hash)
        if existing_photo:
            return {
                "status": "duplicate",
                "photo_id": existing_photo.id,
                "message": f"Photo already exists: {existing_photo.filename}",
                "existing_path": existing_photo.file_path
            }
        
        try:
            # Extract metadata first (before storage)
            metadata_result = await self._extract_metadata_from_content(file_content, filename)
            
            # Store file using storage backend
            storage_result = await self.storage.store_file(
                file_content, 
                filename, 
                content_type, 
                metadata_result
            )
            
            if not storage_result.success:
                if storage_result.is_duplicate:
                    # Handle storage-level duplicate
                    return {
                        "status": "duplicate",
                        "message": "File already exists in storage",
                        "storage_path": storage_result.storage_path
                    }
                else:
                    return {
                        "status": "error",
                        "error": storage_result.error_message
                    }
            
            # Create database records
            photo_record = await self._create_photo_record(
                db_session,
                storage_result.storage_path,
                file_hash,
                filename,
                content_type,
                len(file_content),
                metadata_result
            )
            
            await db_session.commit()
            
            return {
                "status": "success",
                "photo_id": photo_record.id,
                "filename": filename,
                "storage_path": storage_result.storage_path,
                "file_size": len(file_content),
                "file_hash": file_hash,
                "processing_status": photo_record.processing_status,
                "processing_stage": photo_record.processing_stage,
                "metadata_extracted": bool(metadata_result)
            }
            
        except Exception as e:
            await db_session.rollback()
            # Attempt cleanup of stored file if it was saved
            if 'storage_result' in locals() and storage_result.success:
                await self.storage.delete_file(storage_result.storage_path)
            
            return {
                "status": "error",
                "error": f"Upload processing failed: {str(e)}"
            }

    async def process_batch_upload(
        self,
        files_data: List[Tuple[bytes, str, str]],  # (content, filename, content_type)
        db_session: AsyncSession
    ) -> Dict:
        """Process multiple photo uploads in batch."""
        
        results = []
        successful_uploads = 0
        duplicate_count = 0
        error_count = 0
        
        for file_content, filename, content_type in files_data:
            try:
                result = await self.process_upload(file_content, filename, content_type, db_session)
                results.append({
                    "filename": filename,
                    **result
                })
                
                if result["status"] == "success":
                    successful_uploads += 1
                elif result["status"] == "duplicate":
                    duplicate_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                results.append({
                    "filename": filename,
                    "status": "error",
                    "error": str(e)
                })
                error_count += 1
        
        return {
            "total_files": len(files_data),
            "successful_uploads": successful_uploads,
            "duplicate_files": duplicate_count,
            "errors": error_count,
            "results": results
        }

    async def get_photo_content(self, photo_id: str, db_session: AsyncSession) -> Optional[bytes]:
        """Retrieve photo content from storage."""
        from sqlalchemy import select
        
        stmt = select(Photo).where(Photo.id == photo_id)
        result = await db_session.execute(stmt)
        photo = result.scalar_one_or_none()
        
        if not photo:
            return None
        
        return await self.storage.retrieve_file(photo.file_path)

    async def delete_photo(self, photo_id: str, db_session: AsyncSession) -> bool:
        """Delete photo from both storage and database."""
        from sqlalchemy import select
        
        stmt = select(Photo).where(Photo.id == photo_id)
        result = await db_session.execute(stmt)
        photo = result.scalar_one_or_none()
        
        if not photo:
            return False
        
        try:
            # Delete from storage
            storage_deleted = await self.storage.delete_file(photo.file_path)
            
            # Delete from database
            await db_session.delete(photo)
            await db_session.commit()
            
            return storage_deleted
        except Exception:
            await db_session.rollback()
            return False

    async def _check_existing_photo(self, db_session: AsyncSession, file_hash: str) -> Optional[Photo]:
        """Check if a photo with the same hash already exists."""
        from sqlalchemy import select
        
        stmt = select(Photo).where(Photo.file_hash == file_hash)
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def _extract_metadata_from_content(self, file_content: bytes, filename: str) -> Optional[Dict]:
        """Extract metadata from file content without saving to disk first."""
        try:
            # For now, we'll use a temporary file approach
            # In the future, we could implement in-memory metadata extraction
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as tmp_file:
                tmp_file.write(file_content)
                tmp_file.flush()
                
                # Use existing PhotoProcessor
                result = await self.photo_processor.process_photo_async(tmp_file.name)
                
                # Clean up temp file
                Path(tmp_file.name).unlink()
                
                if result.get("success") and result.get("metadata"):
                    return result["metadata"]
                return None
                
        except Exception as e:
            print(f"Metadata extraction failed for {filename}: {e}")
            return None

    async def _create_photo_record(
        self,
        db_session: AsyncSession,
        storage_path: str,
        file_hash: str,
        filename: str,
        content_type: str,
        file_size: int,
        metadata_result: Optional[Dict]
    ) -> Photo:
        """Create Photo and PhotoMetadata database records."""
        
        # Extract basic image dimensions from metadata if available
        width = height = None
        file_modified = datetime.utcnow()
        
        if metadata_result:
            width = metadata_result.get("width")
            height = metadata_result.get("height")
            if metadata_result.get("file_modified"):
                file_modified = metadata_result["file_modified"]
        
        # Create Photo record
        photo = Photo(
            id=str(uuid4()),
            file_path=storage_path,  # This is now the storage path, not filesystem path
            file_hash=file_hash,
            filename=filename,
            file_size=file_size,
            file_modified=file_modified,
            mime_type=content_type,
            file_extension=Path(filename).suffix.lower(),
            width=width,
            height=height,
            processing_status="completed",  # Successfully stored and metadata extracted
            processing_stage="incoming",    # V2 workflow stage
            priority_level=0,
            needs_attention=True
        )
        
        db_session.add(photo)
        await db_session.flush()  # Get the photo ID
        
        # Create PhotoMetadata record if metadata was extracted
        if metadata_result:
            photo_metadata = PhotoMetadata(
                id=str(uuid4()),
                photo_id=photo.id,
                camera_make=metadata_result.get("camera_make"),
                camera_model=metadata_result.get("camera_model"),
                lens_model=metadata_result.get("lens_model"),
                focal_length=metadata_result.get("focal_length"),
                aperture=metadata_result.get("aperture"),
                shutter_speed=metadata_result.get("shutter_speed"),
                iso=metadata_result.get("iso"),
                flash=metadata_result.get("flash"),
                exposure_mode=metadata_result.get("exposure_mode"),
                metering_mode=metadata_result.get("metering_mode"),
                white_balance=metadata_result.get("white_balance"),
                date_taken=metadata_result.get("date_taken"),
                date_digitized=metadata_result.get("date_digitized"),
                date_modified=metadata_result.get("date_modified"),
                gps_latitude=metadata_result.get("gps_latitude"),
                gps_longitude=metadata_result.get("gps_longitude"),
                gps_altitude=metadata_result.get("gps_altitude"),
                gps_direction=metadata_result.get("gps_direction"),
                color_space=metadata_result.get("color_space"),
                orientation=metadata_result.get("orientation"),
                resolution_x=metadata_result.get("resolution_x"),
                resolution_y=metadata_result.get("resolution_y"),
                resolution_unit=metadata_result.get("resolution_unit"),
                software=metadata_result.get("software"),
                artist=metadata_result.get("artist"),
                copyright=metadata_result.get("copyright"),
                raw_exif=metadata_result.get("raw_exif", {})
            )
            
            db_session.add(photo_metadata)
        
        return photo

    def get_storage_info(self) -> Dict:
        """Get information about the current storage backend."""
        if hasattr(self.storage, 'get_storage_stats'):
            return self.storage.get_storage_stats()
        else:
            return {
                "backend_type": type(self.storage).__name__,
                "config": {
                    "base_path": str(self.storage.config.base_path),
                    "organize_by_date": self.storage.config.organize_by_date,
                    "use_content_hash": self.storage.config.use_content_hash
                }
            }