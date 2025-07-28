import asyncio
import logging
from enum import Enum
from pathlib import Path

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


class PreviewSize(Enum):
    """Supported preview sizes."""

    THUMBNAIL = "thumbnail"  # 150px max dimension
    SMALL = "small"  # 400px max dimension
    MEDIUM = "medium"  # 800px max dimension
    LARGE = "large"  # 1200px max dimension


class PreviewGenerator:
    """Service for generating and managing photo previews/thumbnails."""

    SIZE_DIMENSIONS = {
        PreviewSize.THUMBNAIL: 150,
        PreviewSize.SMALL: 400,
        PreviewSize.MEDIUM: 800,
        PreviewSize.LARGE: 1200,
    }

    def __init__(self, base_preview_path: Path | None = None):
        """Initialize preview generator with configurable base path."""
        self.base_preview_path = base_preview_path or Path("./uploads/previews")
        self.base_preview_path.mkdir(parents=True, exist_ok=True)

        # Preview quality settings
        self.jpeg_quality = 85
        self.webp_quality = 85

    def _get_preview_path(
        self, photo_id: str, size: PreviewSize, format: str = "jpg"
    ) -> Path:
        """Generate preview file path."""
        # Organize previews by photo ID prefix for better filesystem performance
        prefix = photo_id[:2]
        preview_dir = self.base_preview_path / prefix
        preview_dir.mkdir(parents=True, exist_ok=True)

        return preview_dir / f"{photo_id}_{size.value}.{format}"

    def _calculate_dimensions(
        self, original_size: tuple[int, int], target_size: int
    ) -> tuple[int, int]:
        """Calculate optimal preview dimensions maintaining aspect ratio."""
        width, height = original_size

        # Calculate scaling factor to fit within target size
        scale_factor = min(target_size / width, target_size / height)

        # Don't upscale - only downscale
        if scale_factor > 1.0:
            scale_factor = 1.0

        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)

        return (new_width, new_height)

    async def generate_preview(
        self,
        original_image_path: Path,
        photo_id: str,
        size: PreviewSize,
        format: str = "jpg",
    ) -> Path | None:
        """Generate a preview image for the given photo."""

        def _generate_sync():
            try:
                target_dimension = self.SIZE_DIMENSIONS[size]
                preview_path = self._get_preview_path(photo_id, size, format)

                # Check if preview already exists
                if preview_path.exists():
                    logger.debug(f"Preview already exists: {preview_path}")
                    return preview_path

                # Open and process image
                with Image.open(original_image_path) as img:
                    # Convert to RGB if necessary (handles RGBA, P, etc.)
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")

                    # Apply EXIF orientation
                    img = ImageOps.exif_transpose(img)

                    # Calculate target dimensions
                    new_dimensions = self._calculate_dimensions(
                        img.size, target_dimension
                    )

                    # Resize with high quality
                    img_resized = img.resize(new_dimensions, Image.Resampling.LANCZOS)

                    # Save with appropriate format and quality
                    if format.lower() == "webp":
                        img_resized.save(
                            preview_path,
                            format="WebP",
                            quality=self.webp_quality,
                            optimize=True,
                        )
                    else:
                        img_resized.save(
                            preview_path,
                            format="JPEG",
                            quality=self.jpeg_quality,
                            optimize=True,
                        )

                    logger.info(f"Generated {size.value} preview: {preview_path}")
                    return preview_path

            except Exception as e:
                logger.error(f"Failed to generate preview for {photo_id}: {e}")
                return None

        # Run synchronous image processing in thread pool
        return await asyncio.get_event_loop().run_in_executor(None, _generate_sync)

    async def generate_all_previews(
        self, original_image_path: Path, photo_id: str
    ) -> dict[str, Path | None]:
        """Generate all preview sizes for a photo."""
        results = {}

        # Generate previews concurrently
        tasks = []
        for size in PreviewSize:
            task = self.generate_preview(original_image_path, photo_id, size)
            tasks.append((size.value, task))

        # Wait for all tasks to complete
        for size_name, task in tasks:
            preview_path = await task
            results[size_name] = preview_path

        return results

    async def get_preview_path(
        self, photo_id: str, size: PreviewSize, format: str = "jpg"
    ) -> Path | None:
        """Get existing preview path or None if it doesn't exist."""
        preview_path = self._get_preview_path(photo_id, size, format)
        return preview_path if preview_path.exists() else None

    async def get_or_generate_preview(
        self,
        original_image_path: Path,
        photo_id: str,
        size: PreviewSize,
        format: str = "jpg",
    ) -> Path | None:
        """Get existing preview or generate if it doesn't exist."""
        # Check if preview already exists
        existing_path = await self.get_preview_path(photo_id, size, format)
        if existing_path:
            return existing_path

        # Generate new preview
        return await self.generate_preview(original_image_path, photo_id, size, format)

    async def delete_previews(self, photo_id: str) -> bool:
        """Delete all preview files for a photo."""
        try:
            deleted_count = 0

            # Check all possible sizes and formats
            for size in PreviewSize:
                for format in ["jpg", "webp"]:
                    preview_path = self._get_preview_path(photo_id, size, format)
                    if preview_path.exists():
                        preview_path.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted preview: {preview_path}")

            logger.info(f"Deleted {deleted_count} preview files for photo {photo_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete previews for photo {photo_id}: {e}")
            return False

    def get_preview_info(self, photo_id: str) -> dict[str, dict]:
        """Get information about existing previews for a photo."""
        info = {}

        for size in PreviewSize:
            size_info = {}
            for format in ["jpg", "webp"]:
                preview_path = self._get_preview_path(photo_id, size, format)
                if preview_path.exists():
                    stat = preview_path.stat()
                    size_info[format] = {
                        "path": str(preview_path),
                        "size_bytes": stat.st_size,
                        "modified": stat.st_mtime,
                    }

            if size_info:
                info[size.value] = size_info

        return info

    def cleanup_orphaned_previews(self, valid_photo_ids: set) -> int:
        """Remove preview files for photos that no longer exist."""
        removed_count = 0

        try:
            # Scan all preview directories
            for prefix_dir in self.base_preview_path.iterdir():
                if not prefix_dir.is_dir():
                    continue

                for preview_file in prefix_dir.glob("*_*.jpg"):
                    # Extract photo ID from filename
                    photo_id = preview_file.stem.split("_")[0]

                    if photo_id not in valid_photo_ids:
                        preview_file.unlink()
                        removed_count += 1
                        logger.debug(f"Removed orphaned preview: {preview_file}")

            logger.info(
                f"Cleanup complete: removed {removed_count} orphaned preview files"
            )
            return removed_count

        except Exception as e:
            logger.error(f"Preview cleanup failed: {e}")
            return 0

    def get_storage_stats(self) -> dict:
        """Get storage statistics for the preview system."""
        stats = {
            "total_files": 0,
            "total_size_bytes": 0,
            "size_breakdown": {},
            "base_path": str(self.base_preview_path),
        }

        try:
            for size in PreviewSize:
                stats["size_breakdown"][size.value] = {"count": 0, "size_bytes": 0}

            # Scan all preview files
            for preview_file in self.base_preview_path.rglob("*_*.jpg"):
                if preview_file.is_file():
                    stats["total_files"] += 1
                    file_size = preview_file.stat().st_size
                    stats["total_size_bytes"] += file_size

                    # Determine size category from filename
                    size_name = preview_file.stem.split("_")[1]
                    if size_name in stats["size_breakdown"]:
                        stats["size_breakdown"][size_name]["count"] += 1
                        stats["size_breakdown"][size_name]["size_bytes"] += file_size

        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")

        return stats
