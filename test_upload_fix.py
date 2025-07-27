#!/usr/bin/env python3
"""Test script to verify upload fix without starting full server."""

import asyncio
import tempfile
from pathlib import Path

# Create a simple test image
from PIL import Image


async def test_upload_components():
    """Test the core upload components to verify greenlet fix."""

    # Create a test image
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
        # Create a simple RGB image
        img = Image.new("RGB", (100, 100), color="red")
        img.save(tmp_file.name)
        tmp_path = Path(tmp_file.name)

    try:
        # Test PhotoProcessorService async method
        from src.core.services.photo_processor_service import PhotoProcessorService

        processor = PhotoProcessorService()
        print("Testing PhotoProcessorService.process_photo_async...")

        result = await processor.process_photo_async(str(tmp_path))

        if result["success"]:
            print("✅ Metadata extraction working!")
            print(
                f"   Dimensions: {result['metadata']['width']}x{result['metadata']['height']}"
            )
            print(f"   File size: {result['metadata']['file_size']} bytes")
        else:
            print(f"❌ Metadata extraction failed: {result['error']}")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Clean up test file
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(test_upload_components())
