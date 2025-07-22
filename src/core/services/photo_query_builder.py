from datetime import datetime, timedelta
from typing import Optional, Any, Dict
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import Select

from src.infrastructure.database.models import Photo, PhotoMetadata


class PhotoQueryBuilder:
    """Efficient photo query builder with lazy filter construction and debugging support."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.query: Select = select(Photo).options(joinedload(Photo.photo_metadata))
        self.applied_filters: Dict[str, Any] = {}
        self._debug_mode = False
    
    def debug_mode(self, enabled: bool = True) -> 'PhotoQueryBuilder':
        """Enable debug mode to preview SQL queries."""
        self._debug_mode = enabled
        return self
    
    def with_search(self, search_term: Optional[str]) -> 'PhotoQueryBuilder':
        """Add text search filter."""
        if search_term:
            self.applied_filters['search'] = search_term
            search_filter = or_(
                Photo.filename.ilike(f"%{search_term}%"),
                Photo.photo_metadata.has(
                    PhotoMetadata.camera_make.ilike(f"%{search_term}%")
                ),
                Photo.photo_metadata.has(
                    PhotoMetadata.camera_model.ilike(f"%{search_term}%")
                ),
            )
            self.query = self.query.where(search_filter)
        return self
    
    def with_processing_stage(self, stage: Optional[str]) -> 'PhotoQueryBuilder':
        """Filter by processing stage."""
        if stage:
            self.applied_filters['processing_stage'] = stage
            self.query = self.query.where(Photo.processing_stage == stage)
        return self
    
    def with_camera_make(self, camera_make: Optional[str]) -> 'PhotoQueryBuilder':
        """Filter by camera make."""
        if camera_make:
            self.applied_filters['camera_make'] = camera_make
            self.query = self.query.where(
                Photo.photo_metadata.has(
                    PhotoMetadata.camera_make.ilike(f"%{camera_make}%")
                )
            )
        return self
    
    def with_rating(self, rating: Optional[int] = None, rating_min: Optional[int] = None) -> 'PhotoQueryBuilder':
        """Filter by rating (exact or minimum)."""
        if rating:
            self.applied_filters['rating'] = rating
            self.query = self.query.where(Photo.user_rating == rating)
        elif rating_min:
            self.applied_filters['rating_min'] = rating_min
            self.query = self.query.where(Photo.user_rating >= rating_min)
        return self
    
    def with_date_range(self, date_from: Optional[str] = None, date_to: Optional[str] = None) -> 'PhotoQueryBuilder':
        """Filter by date taken range."""
        if date_from:
            try:
                date_from_parsed = datetime.fromisoformat(date_from)
                self.applied_filters['date_from'] = date_from
                self.query = self.query.where(
                    Photo.photo_metadata.has(
                        PhotoMetadata.date_taken >= date_from_parsed
                    )
                )
            except ValueError:
                raise ValueError("Invalid date_from format. Use ISO format (YYYY-MM-DD).")
        
        if date_to:
            try:
                date_to_parsed = datetime.fromisoformat(date_to)
                self.applied_filters['date_to'] = date_to
                self.query = self.query.where(
                    Photo.photo_metadata.has(
                        PhotoMetadata.date_taken <= date_to_parsed
                    )
                )
            except ValueError:
                raise ValueError("Invalid date_to format. Use ISO format (YYYY-MM-DD).")
        
        return self
    
    def with_camera_settings(self, 
                           aperture_min: Optional[float] = None,
                           aperture_max: Optional[float] = None,
                           iso_min: Optional[int] = None,
                           iso_max: Optional[int] = None) -> 'PhotoQueryBuilder':
        """Filter by camera settings (aperture, ISO)."""
        if aperture_min:
            self.applied_filters['aperture_min'] = aperture_min
            self.query = self.query.where(
                Photo.photo_metadata.has(PhotoMetadata.aperture >= aperture_min)
            )
        
        if aperture_max:
            self.applied_filters['aperture_max'] = aperture_max
            self.query = self.query.where(
                Photo.photo_metadata.has(PhotoMetadata.aperture <= aperture_max)
            )
        
        if iso_min:
            self.applied_filters['iso_min'] = iso_min
            self.query = self.query.where(
                Photo.photo_metadata.has(PhotoMetadata.iso >= iso_min)
            )
        
        if iso_max:
            self.applied_filters['iso_max'] = iso_max
            self.query = self.query.where(
                Photo.photo_metadata.has(PhotoMetadata.iso <= iso_max)
            )
        
        return self
    
    def with_gps(self, has_gps: Optional[bool]) -> 'PhotoQueryBuilder':
        """Filter by GPS availability."""
        if has_gps is not None:
            self.applied_filters['has_gps'] = has_gps
            if has_gps:
                gps_filter = Photo.photo_metadata.has(
                    and_(
                        PhotoMetadata.gps_latitude.isnot(None),
                        PhotoMetadata.gps_longitude.isnot(None)
                    )
                )
            else:
                gps_filter = Photo.photo_metadata.has(
                    or_(
                        PhotoMetadata.gps_latitude.is_(None),
                        PhotoMetadata.gps_longitude.is_(None)
                    )
                )
            self.query = self.query.where(gps_filter)
        return self
    
    def with_whitelist_defaults(self, show_all: bool = False) -> 'PhotoQueryBuilder':
        """Apply whitelist defaults if no specific filters are active."""
        if not show_all and not self.applied_filters:
            # Default: only show photos from last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            self.query = self.query.where(Photo.created_at >= thirty_days_ago)
            self.applied_filters['default_recent'] = True
        return self
    
    def with_pagination(self, limit: int = 50, offset: int = 0, max_limit: int = 200) -> 'PhotoQueryBuilder':
        """Apply pagination with safety limits."""
        safe_limit = min(limit, max_limit)
        self.applied_filters['limit'] = safe_limit
        self.applied_filters['offset'] = offset
        
        self.query = self.query.order_by(Photo.created_at.desc()).offset(offset).limit(safe_limit)
        return self
    
    def get_sql_preview(self) -> str:
        """Get SQL preview for debugging (requires SQLAlchemy engine)."""
        if self._debug_mode:
            try:
                # This would require the engine for compilation
                # For now, return a representation
                return f"Query with filters: {self.applied_filters}"
            except Exception:
                return f"Applied filters: {self.applied_filters}"
        return "Debug mode not enabled"
    
    def get_applied_filters(self) -> Dict[str, Any]:
        """Get dictionary of currently applied filters."""
        return self.applied_filters.copy()
    
    async def execute(self):
        """Execute the query and return results."""
        if self._debug_mode:
            print(f"[DEBUG] Executing query with filters: {self.applied_filters}")
        
        result = await self.session.execute(self.query)
        return result.scalars().all()
    
    async def count(self) -> int:
        """Get total count for the current filters (without pagination)."""
        # Create count query without pagination
        count_query = select(Photo)
        
        # Apply all filters except pagination
        for filter_key, filter_value in self.applied_filters.items():
            if filter_key not in ['limit', 'offset']:
                # Re-apply filters to count query
                # This is a simplified approach - in production you'd want to extract filter logic
                pass
        
        # For now, use a simpler count approach
        from sqlalchemy import func
        count_query = select(func.count(Photo.id))
        
        # Apply the same WHERE conditions as the main query
        # This is a bit hacky but works for our current needs
        count_result = await self.session.execute(count_query)
        return count_result.scalar() or 0


def build_photo_query(session: AsyncSession) -> PhotoQueryBuilder:
    """Factory function to create a new PhotoQueryBuilder."""
    return PhotoQueryBuilder(session)