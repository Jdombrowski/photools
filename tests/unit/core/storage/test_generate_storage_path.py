import pytest
from datetime import datetime
from src.core.storage.local import LocalStorageBackend
from src.core.storage.base import StorageConfig


class TestGenerateStoragePath:
    def test_generate_storage_path_method_exists(self):
        """Test that generate_storage_path method exists and is callable."""
        config = StorageConfig(base_path='./test_storage')
        backend = LocalStorageBackend(config)
        
        assert hasattr(backend, 'generate_storage_path')
        assert callable(backend.generate_storage_path)
    
    def test_generate_storage_path_with_date_organization(self):
        """Test path generation with date organization enabled."""
        config = StorageConfig(
            base_path='./test_storage',
            organize_by_date=True,
            use_content_hash=True
        )
        backend = LocalStorageBackend(config)
        
        test_date = datetime(2023, 12, 25, 10, 30, 45)
        path = backend.generate_storage_path('test.jpg', 'abc123hash', test_date)
        
        # Should generate path like: 2023/12/25/abc123hash.jpg
        assert path.startswith('2023/12/25/')
        assert path.endswith('abc123hash.jpg')
    
    def test_generate_storage_path_flat_structure(self):
        """Test path generation with flat structure."""
        config = StorageConfig(
            base_path='./test_storage',
            organize_by_date=False,
            use_content_hash=True
        )
        backend = LocalStorageBackend(config)
        
        path = backend.generate_storage_path('test.jpg', 'abc123hash')
        
        # Should generate path like: abc123hash.jpg
        assert path == 'abc123hash.jpg'
    
    def test_generate_storage_path_preserve_names(self):
        """Test path generation with preserved original names."""
        config = StorageConfig(
            base_path='./test_storage',
            organize_by_date=True,
            use_content_hash=False,
            preserve_original_names=True
        )
        backend = LocalStorageBackend(config)
        
        test_date = datetime(2023, 12, 25, 10, 30, 45)
        path = backend.generate_storage_path('original_photo.jpg', 'abc123hash', test_date)
        
        # Should generate path like: 2023/12/25/original_photo_103045.jpg
        assert path.startswith('2023/12/25/')
        assert 'original_photo' in path
        assert path.endswith('.jpg')