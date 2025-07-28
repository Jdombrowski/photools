import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path("./src").resolve()))

from src.infrastructure.database.connection import get_db_session
from src.core.services.service_factory import ServiceFactory


async def test_performance_metrics():
    test_file = Path("./data/DSCF0001.jpg")
    if not test_file.exists():
        print(f"Test file not found: {test_file}")
        return

    service_factory = ServiceFactory()
    import_service = service_factory.get_photo_import_service()

    async for db in get_db_session():
        try:
            result = await import_service.import_single_photo(test_file, db)

            print(f"Import Performance Metrics:")
            print(f"  Status: {result.status}")
            print(f"  Duration: {result.duration_seconds:.3f} seconds")
            print(f"  Success Rate: {result.success_rate:.1f}%")
            print(f"  Processing Speed: {result.files_per_second:.2f} files/sec")
            print(
                f"  Files: {result.imported_files} imported, {result.skipped_files} skipped, {result.failed_files} failed"
            )
            break
        except Exception as e:
            print(f"Error: {e}")
            break


asyncio.run(test_performance_metrics())
