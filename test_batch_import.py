import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path('./src').resolve()))

from src.infrastructure.database.connection import get_db_session
from src.core.services.service_factory import ServiceFactory
from src.core.services.photo_import_service import ImportOptions
from src.core.models.scan_result import ScanResult

async def test_batch_import():
    # Use our existing test data directory
    test_dir = Path('./data')
    if not test_dir.exists():
        print(f'Test directory not found: {test_dir}')
        return
    
    print(f'Testing batch import from: {test_dir}')
    
    # Get services
    service_factory = ServiceFactory()
    import_service = service_factory.get_photo_import_service()
    
    # Import options
    import_options = ImportOptions(
        skip_duplicates=True,
        max_file_size_mb=100,
    )
    
    # Get database session and test batch import
    async for db in get_db_session():
        try:
            print('Starting directory import...')
            result = await import_service.import_directory(test_dir, db, import_options)
            print(f'Directory import result:')
            print(f'  Status: {result.status}')
            print(f'  Total files: {result.total_files}')
            print(f'  Imported: {result.imported_files}')
            print(f'  Skipped: {result.skipped_files}')
            print(f'  Failed: {result.failed_files}')
            if result.error_details:
                print(f'  Errors: {len(result.error_details)}')
                for error in result.error_details[:3]:  # Show first 3 errors
                    print(f'    - {error}')
            break
        except Exception as e:
            print(f'Error: {e}')
            import traceback
            traceback.print_exc()
            break
    
    # Clean up: delete any imported photos for next test run
    print("\nCleaning up imported photos...")
    async for db in get_db_session():
        try:
            from sqlalchemy import select, delete
            from src.infrastructure.database.models import Photo, PhotoMetadata
            
            # Get all photos from the test directory
            photos_in_dir = []
            if test_dir.exists():
                photo_files = list(test_dir.glob('*.jpg'))[:5]  # Match our limit
                for photo_file in photo_files:
                    stmt = select(Photo).where(Photo.filename == photo_file.name)
                    result = await db.execute(stmt)
                    photos = result.scalars().all()
                    photos_in_dir.extend(photos)
                    
            for photo in photos_in_dir:
                # Delete metadata first (foreign key constraint)
                metadata_stmt = delete(PhotoMetadata).where(PhotoMetadata.photo_id == photo.id)
                await db.execute(metadata_stmt)
                
                # Delete photo
                await db.delete(photo)
                print(f"Deleted photo: {photo.filename}")
            
            await db.commit()
            break
        except Exception as e:
            print(f"Cleanup error: {e}")
            break

asyncio.run(test_batch_import())