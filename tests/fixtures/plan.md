# TODO Edge Cases to acquire

  tests/fixtures/
  ├── __init__.py
  ├── photos/             # Small test images
  │   ├── valid_jpg.jpg   # 50KB, basic EXIF
  │   ├── no_exif.jpg     # Photo without metadata
  │   ├── raw_file.cr2    # RAW format test
  │   └── invalid.txt     # Non-photo file
  ├── metadata/           # Known metadata samples
  │   ├── sample_exif.json
  │   └── expected_results.json
  └── configs/            # Test configurations
      ├── minimal_settings.py
      └── security_test_settings.py
