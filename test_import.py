import asyncio                                                                                    
import sys                                                                                        
from pathlib import Path                                                                          
                                                                                                  
# Add src to path                                                                                 
sys.path.insert(0, str(Path('./src').resolve()))                                                  
                                                                                                  
from src.infrastructure.database.connection import get_db_session                                     
from src.core.services.photo_import_service import PhotoImportService                                 
from src.config.settings import get_settings                                                          
from src.core.services.service_factory import ServiceFactory                                          
                                                                                                  
async def test_import():                                                                          
    # Test with different files to check both duplicate and fresh import
    test_files = [
        Path('./data/DSCF0001.jpg'),  # Likely a duplicate
        Path('./data/DSCF0002.jpg'),  # Try a fresh import
    ]
    
    # Get services
    service_factory = ServiceFactory()
    import_service = service_factory.get_photo_import_service()

    for test_file in test_files:
        if not test_file.exists():
            print(f'Test file not found: {test_file}')
            continue

        print(f'\nTesting with file: {test_file}')

        # Get database session
        async for db in get_db_session():
            try:
                print('Testing single photo import...')
                result = await import_service.import_single_photo(test_file, db)
                print(f'Result: {result}')
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
            
            # Delete photos that were just imported (by filename)
            for test_file in test_files:
                if test_file.exists():
                    stmt = select(Photo).where(Photo.filename == test_file.name)
                    result = await db.execute(stmt)
                    photos = result.scalars().all()
                    
                    for photo in photos:
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
                                                                                                  
asyncio.run(test_import())