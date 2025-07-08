from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class ProcessingStage(Enum):
    """Photo processing stages for progressive workflow (V2 feature)."""

    INCOMING = "incoming"  # Just imported, needs first review
    REVIEWED = "reviewed"  # Quick preview done, kept/rejected
    BASIC_EDIT = "basic_edit"  # Exposure/basic corrections applied
    CURATED = "curated"  # Selected as "good enough to work on"
    REFINED = "refined"  # Detailed editing in progress
    FINAL = "final"  # Ready for delivery/export
    REJECTED = "rejected"  # Marked for deletion/archive


class Photo(Base):
    """Core photo entity with file information and metadata."""

    __tablename__ = "photos"

    # Primary identifiers
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    file_path = Column(String, nullable=False, unique=True, index=True)
    file_hash = Column(String, nullable=False, index=True)
    filename = Column(String, nullable=False)

    # File metadata
    file_size = Column(Integer, nullable=False)
    file_modified = Column(DateTime, nullable=False)
    mime_type = Column(String, nullable=False)
    file_extension = Column(String, nullable=False)

    # Image dimensions
    width = Column(Integer)
    height = Column(Integer)

    # Processing status
    processing_status = Column(
        String, default="pending"
    )  # pending, processing, completed, failed
    processing_error = Column(Text)

    # V2: Progressive workflow fields
    processing_stage = Column(String, default="incoming")  # ProcessingStage enum values
    priority_level = Column(Integer, default=0)  # 0=normal, 1=good, 2=excellent
    needs_attention = Column(Boolean, default=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    photo_metadata = relationship(
        "PhotoMetadata",
        back_populates="photo",
        uselist=False,
        cascade="all, delete-orphan",
    )
    tags = relationship(
        "PhotoTag", back_populates="photo", cascade="all, delete-orphan"
    )
    ai_analysis = relationship(
        "PhotoAIAnalysis", back_populates="photo", cascade="all, delete-orphan"
    )
    scan_entries = relationship(
        "ScanPhotoEntry", back_populates="photo", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Photo(id={self.id}, filename={self.filename}, status={self.processing_status})>"


class PhotoMetadata(Base):
    """EXIF and other technical metadata extracted from photos."""

    __tablename__ = "photo_metadata"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    photo_id = Column(
        String, ForeignKey("photos.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Camera information
    camera_make = Column(String)
    camera_model = Column(String)
    lens_model = Column(String)

    # Capture settings
    focal_length = Column(Float)
    aperture = Column(Float)
    shutter_speed = Column(String)
    iso = Column(Integer)
    flash = Column(String)
    exposure_mode = Column(String)
    metering_mode = Column(String)
    white_balance = Column(String)

    # Timestamp information
    date_taken = Column(DateTime, index=True)
    date_digitized = Column(DateTime)
    date_modified = Column(DateTime)

    # GPS coordinates (WGS84)
    gps_latitude = Column(Float, index=True)
    gps_longitude = Column(Float, index=True)
    gps_altitude = Column(Float)
    gps_direction = Column(Float)

    # Image technical details
    color_space = Column(String)
    orientation = Column(Integer)
    resolution_x = Column(Float)
    resolution_y = Column(Float)
    resolution_unit = Column(String)

    # Software and processing
    software = Column(String)
    artist = Column(String)
    copyright = Column(String)

    # Raw EXIF data (JSON storage for complete metadata)
    raw_exif = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    photo = relationship("Photo", back_populates="photo_metadata")

    def __repr__(self):
        return f"<PhotoMetadata(photo_id={self.photo_id}, camera={self.camera_make} {self.camera_model})>"


class PhotoTag(Base):
    """Tags associated with photos (user-generated or AI-generated)."""

    __tablename__ = "photo_tags"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    photo_id = Column(
        String, ForeignKey("photos.id", ondelete="CASCADE"), nullable=False, index=True
    )

    tag = Column(String, nullable=False, index=True)
    tag_type = Column(String, default="manual")  # manual, ai_generated, extracted
    confidence = Column(Float)  # For AI-generated tags
    source = Column(String)  # Which system/model generated the tag

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    photo = relationship("Photo", back_populates="tags")

    # Ensure no duplicate tags per photo
    __table_args__ = (
        UniqueConstraint("photo_id", "tag", "tag_type", name="unique_photo_tag"),
    )

    def __repr__(self):
        return f"<PhotoTag(photo_id={self.photo_id}, tag={self.tag}, type={self.tag_type})>"


class PhotoAIAnalysis(Base):
    """AI-generated analysis results for photos."""

    __tablename__ = "photo_ai_analysis"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    photo_id = Column(
        String, ForeignKey("photos.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Analysis metadata
    analysis_type = Column(
        String, nullable=False
    )  # embedding, object_detection, scene_classification
    model_name = Column(String, nullable=False)
    model_version = Column(String)
    confidence_threshold = Column(Float)

    # Results (stored as JSON for flexibility)
    results = Column(JSON, nullable=False)

    # Vector embeddings (for semantic search)
    embedding_vector = Column(JSON)  # Will store as array of floats
    embedding_dimensions = Column(Integer)

    # Processing information
    processing_time_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    photo = relationship("Photo", back_populates="ai_analysis")

    def __repr__(self):
        return f"<PhotoAIAnalysis(photo_id={self.photo_id}, type={self.analysis_type}, model={self.model_name})>"


class DirectoryScan(Base):
    """Record of directory scanning operations."""

    __tablename__ = "directory_scans"

    # Basic scan information
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    scan_id = Column(
        String, nullable=False, unique=True, index=True
    )  # External scan identifier
    directory_path = Column(String, nullable=False, index=True)

    # Scan configuration
    scan_strategy = Column(
        String, nullable=False
    )  # fast_metadata_only, full_metadata, incremental
    scan_options = Column(JSON)  # Store ScanOptions as JSON

    # Status and progress
    status = Column(
        String, nullable=False, default="pending"
    )  # pending, running, completed, failed, cancelled
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    successful_files = Column(Integer, default=0)
    failed_files = Column(Integer, default=0)

    # Timing information
    start_time = Column(DateTime, index=True)
    end_time = Column(DateTime)
    estimated_completion = Column(DateTime)

    # Results and diagnostics
    errors = Column(JSON)  # List of error messages
    directory_stats = Column(JSON)  # Additional directory statistics

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    photo_entries = relationship(
        "ScanPhotoEntry", back_populates="scan", cascade="all, delete-orphan"
    )

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate scan duration in seconds."""
        start_time = getattr(self, "start_time", None)
        end_time = getattr(self, "end_time", None)
        if start_time is not None and end_time is not None:
            return (end_time - start_time).total_seconds()
        return None

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        processed = getattr(self, "processed_files", 0)
        successful = getattr(self, "successful_files", 0)
        
        if not processed:
            return 0.0
        return (successful / processed) * 100

    def __repr__(self):
        return f"<DirectoryScan(id={self.scan_id}, directory={self.directory_path}, status={self.status})>"


class ScanPhotoEntry(Base):
    """Individual photo entries discovered during directory scans."""

    __tablename__ = "scan_photo_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    scan_id = Column(
        String,
        ForeignKey("directory_scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    photo_id = Column(
        String, ForeignKey("photos.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # File discovery information
    discovered_path = Column(String, nullable=False)
    file_size = Column(Integer)
    file_modified = Column(DateTime)

    # Processing status for this entry
    processing_status = Column(
        String, default="discovered"
    )  # discovered, processed, failed, skipped
    processing_error = Column(Text)
    processed_at = Column(DateTime)

    # Relationships
    scan = relationship("DirectoryScan", back_populates="photo_entries")
    photo = relationship("Photo", back_populates="scan_entries")

    def __repr__(self):
        return f"<ScanPhotoEntry(scan_id={self.scan_id}, path={self.discovered_path}, status={self.processing_status})>"


class BatchScan(Base):
    """Record of batch scanning operations across multiple directories."""

    __tablename__ = "batch_scans"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    batch_id = Column(String, nullable=False, unique=True, index=True)

    # Batch configuration
    directories = Column(JSON, nullable=False)  # List of directory paths
    status = Column(String, nullable=False, default="pending")

    # Aggregate statistics
    total_directories = Column(Integer, default=0)
    completed_directories = Column(Integer, default=0)
    failed_directories = Column(Integer, default=0)

    # Timing
    start_time = Column(DateTime, index=True)
    end_time = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<BatchScan(id={self.batch_id}, directories={self.directories}, status={self.status})>"


class ProcessingAction(Base):
    """V2: Track processing actions and stage transitions for progressive workflow."""

    __tablename__ = "processing_actions"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    photo_id = Column(
        String, ForeignKey("photos.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Stage transition tracking
    stage_from = Column(String, index=True)  # ProcessingStage enum values
    stage_to = Column(String, index=True)  # ProcessingStage enum values

    # Action details
    action_type = Column(
        String, nullable=False
    )  # "basic_exposure", "crop", "color_grade", "batch_select"
    parameters = Column(JSON)  # Non-destructive edit parameters
    app_used = Column(String)  # "photools", "lightroom", "photoshop", etc.

    # Processing metadata
    processing_time_ms = Column(Integer)
    batch_id = Column(String, index=True)  # Group related actions together
    user_notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    photo = relationship("Photo")

    def __repr__(self):
        return f"<ProcessingAction(photo_id={self.photo_id}, {self.stage_from}->{self.stage_to}, type={self.action_type})>"
