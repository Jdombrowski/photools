# INSTALL

This installation process is written to be self-healing, and accessible from both top-down and bottom-up mentalities
If you are missing something, the setup scripts will notify you: removing any possibility of confusion, while keeping all agency in the hands of the operator.

No more missing external tools and debugging.

Error messages = slow
Actionable solutions = zero latency setup

Make sure every single element has been tested from a fully fresh install

## External Dependencies (`make install` -> will output all of this to the terminal)

1. Poetry
Package manager for python - chosen for long term complexity and agnostic lock files
`pipx install poetry`

2. Docker
Install Docker, start Desktop application and log into cli
`docker ps`

3. Exiftool
Batch-ran exif parsing tool
`brew install exiftool`

## STRUCTURE

photools/
├── Makefile                     # Main development workflow automation
├── README.md                   # Project documentation with make commands
├── docker-compose.yml          # Multi-service development environment
├── docker-compose.prod.yml     # Production configurationz
├── .env.example               # Environment variables template
├── .gitignore
├── pyproject.toml             # Python dependencies and project config
├── pytest.ini                # Test configuration
├── .pre-commit-config.yaml    # Git hooks for code quality
│
├── src/                       # Application source code
│   ├── __init__.py
│   ├── core/                  # Domain logic (business rules)
│   │   ├── __init__.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── photo.py
│   │   │   ├── metadata.py
│   │   │   └── search.py
│   │   ├── services/          # Business logic services
│   │   │   ├── __init__.py
│   │   │   ├── metadata_extractor.py
│   │   │   ├── ai_pipeline.py
│   │   │   └── search_service.py
│   │   └── ports/             # Interface definitions
│   │       ├── __init__.py
│   │       ├── repositories.py
│   │       └── ai_models.py
│   │
│   ├── infrastructure/        # External dependencies
│   │   ├── __init__.py
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py
│   │   │   ├── repositories.py
│   │   │   └── models.py
│   │   ├── ai/
│   │   │   ├── __init__.py
│   │   │   ├── model_router.py
│   │   │   ├── embedding_models.py
│   │   │   └── vision_models.py
│   │   ├── external/
│   │   │   ├── __init__.py
│   │   │   ├── exiftool.py
│   │   │   └── file_watcher.py
│   │   └── vector_store/
│   │       ├── __init__.py
│   │       └── chroma_store.py
│   │
│   ├── api/                   # Web interface
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI application
│   │   ├── dependencies.py   # Dependency injection
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── photos.py
│   │   │   ├── search.py
│   │   │   └── health.py
│   │   └── middleware/
│   │       ├── __init__.py
│   │       ├── logging.py
│   │       └── metrics.py
│   │
│   ├── workers/               # Background tasks
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   ├── photo_processor.py
│   │   └── model_indexer.py
│   │
│   └── config/                # Configuration management
│       ├── __init__.py
│       ├── settings.py
│       └── logging.py
│
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── conftest.py           # Pytest configuration and fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── core/
│   │   │   ├── test_models.py
│   │   │   └── test_services.py
│   │   └── infrastructure/
│   │       ├── test_model_router.py
│   │       └── test_repositories.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_api.py
│   │   ├── test_database.py
│   │   └── test_ai_pipeline.py
│   └── fixtures/
│       ├── sample_photos/
│       └── test_data.json
│
├── migrations/                # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── deployments/              # Deployment configurations
│   ├── docker/
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.worker
│   │   └── Dockerfile.nginx
│   ├── kubernetes/
│   │   ├── namespace.yaml
│   │   ├── api-deployment.yaml
│   │   ├── worker-deployment.yaml
│   │   └── services.yaml
│   └── scripts/
│       ├── init-db.sh
│       ├── download-models.sh
│       └── backup-data.sh
│
├── docs/                     # Documentation
│   ├── api/                  # API documentation
│   ├── architecture/         # System design docs
│   ├── deployment/           # Deployment guides
│   └── development/          # Developer guides
│
├── scripts/                  # Utility scripts
│   ├── setup.sh             # Initial project setup
│   ├── check-dependencies.sh # Verify system requirements
│   ├── generate-sample-data.py
│   └── benchmark-models.py
│
└── uploads/                  # Local photo storage (gitignored)
    └── .gitkeep
