"""Photools background workers module

This module contains Celery workers for:
- Photo processing and metadata extraction
- AI model inference and feature extraction
- Search indexing and database updates
"""

from .celery_app import celery_app
from .model_indexer import (
    batch_process_ai_features,
    extract_ai_features,
    generate_embeddings,
    update_search_index,
)
from .photo_processor import process_batch_photos, process_single_photo, scan_directory

__all__ = [
    "celery_app",
    "process_single_photo",
    "process_batch_photos",
    "scan_directory",
    "generate_embeddings",
    "extract_ai_features",
    "batch_process_ai_features",
    "update_search_index",
]
