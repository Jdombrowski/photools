import logging
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from .photo_upload_service import PhotoUploadService
from .preview_generator import PreviewGenerator, PreviewSize

logger = logging.getLogger(__name__)


class PreviewService:
    """Simple service for handling photo preview requests."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.preview_generator = PreviewGenerator()
        self.upload_service = PhotoUploadService()

    async def get_or_generate_preview(
        self,
        photo_id: str,
        size: str = "medium",
        format: str = "jpg",
        is_user_request: bool = True
    ) -> FileResponse:
        """
        Get existing preview or generate if needed.
        
        Args:
            photo_id: Photo identifier
            size: Preview size (thumbnail, small, medium, large)
            format: Image format (jpg, webp)
            is_user_request: True for user clicks, False for background/bulk
        """
        # Validate parameters
        try:
            preview_size = PreviewSize(size)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid size. Must be one of: {', '.join([s.value for s in PreviewSize])}"
            )

        if format not in ["jpg", "webp"]:
            raise HTTPException(status_code=400, detail="Format must be 'jpg' or 'webp'")

        # Get photo from database
        photo = await self._get_photo_or_404(photo_id)

        # Check if preview already exists
        existing_preview = await self.preview_generator.get_preview_path(photo_id, preview_size, format)
        if existing_preview:
            return self._create_file_response(existing_preview, photo.filename, size, format)

        # Generate preview - simple priority logic
        if is_user_request:
            # For user requests, generate immediately and wait briefly
            return await self._generate_urgent_preview(photo, preview_size, format)
        else:
            # For background requests, queue with normal priority
            return await self._queue_background_preview(photo, preview_size, format)

    async def _get_photo_or_404(self, photo_id: str):
        """Get photo from database or raise 404."""
        from sqlalchemy import select

        from src.infrastructure.database.models import Photo

        stmt = select(Photo).where(Photo.id == photo_id)
        result = await self.db.execute(stmt)
        photo = result.scalar_one_or_none()

        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")

        return photo

    async def _generate_urgent_preview(self, photo, preview_size: PreviewSize, format: str) -> FileResponse:
        """Generate preview immediately for user requests."""
        try:
            # Get original file content
            original_content = await self.upload_service.get_photo_content(photo.id, self.db)
            if not original_content:
                raise HTTPException(status_code=404, detail="Original photo file not found")

            # Generate preview using temporary file
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=Path(photo.filename).suffix, delete=False) as tmp_file:
                tmp_file.write(original_content)
                tmp_file.flush()

                preview_path = await self.preview_generator.generate_preview(
                    Path(tmp_file.name), photo.id, preview_size, format
                )

                # Clean up temp file
                Path(tmp_file.name).unlink()

                if preview_path and preview_path.exists():
                    return self._create_file_response(preview_path, photo.filename, preview_size.value, format)
                else:
                    raise HTTPException(status_code=500, detail="Failed to generate preview")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Preview generation failed for photo {photo.id}: {e}")
            raise HTTPException(status_code=500, detail="Preview generation failed")

    async def _queue_background_preview(self, photo, preview_size: PreviewSize, format: str) -> FileResponse:
        """Queue preview generation for background requests."""
        # For now, just generate immediately since we're keeping it simple
        # Could add actual background queueing later if needed
        return await self._generate_urgent_preview(photo, preview_size, format)

    def _create_file_response(self, preview_path: Path, filename: str, size: str, format: str) -> FileResponse:
        """Create a FileResponse for the preview."""
        return FileResponse(
            path=preview_path,
            media_type=f"image/{format}",
            headers={
                "Content-Disposition": f'inline; filename="{filename}_{size}.{format}"',
                "Cache-Control": "public, max-age=31536000"  # Cache for 1 year
            }
        )

    async def generate_all_previews_for_photo(self, photo_id: str) -> dict:
        """Generate all preview sizes for a photo (admin/background use)."""
        photo = await self._get_photo_or_404(photo_id)

        try:
            # Get original file content
            original_content = await self.upload_service.get_photo_content(photo.id, self.db)
            if not original_content:
                raise HTTPException(status_code=404, detail="Original photo file not found")

            # Generate all previews
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=Path(photo.filename).suffix, delete=False) as tmp_file:
                tmp_file.write(original_content)
                tmp_file.flush()

                results = await self.preview_generator.generate_all_previews(Path(tmp_file.name), photo.id)

                # Clean up temp file
                Path(tmp_file.name).unlink()

                successful_previews = {
                    size: str(path) if path else None
                    for size, path in results.items()
                    if path
                }

                return {
                    "photo_id": photo.id,
                    "filename": photo.filename,
                    "generated_previews": successful_previews,
                    "total_generated": len(successful_previews)
                }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Preview generation failed for photo {photo.id}: {e}")
            raise HTTPException(status_code=500, detail="Preview generation failed")

    async def delete_photo_previews(self, photo_id: str) -> bool:
        """Delete all previews for a photo."""
        return await self.preview_generator.delete_previews(photo_id)

    def get_preview_info(self, photo_id: str) -> dict:
        """Get information about existing previews for a photo."""
        return self.preview_generator.get_preview_info(photo_id)

    def get_storage_stats(self) -> dict:
        """Get preview storage statistics."""
        return self.preview_generator.get_storage_stats()
