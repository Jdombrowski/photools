# Photools - Development Automation
# Usage: make <target>
# Run 'make help' to see all available targets

.PHONY: help install dev test clean build deploy

# Default Python and Poetry settings
PYTHON_VERSION ?= 3.11
POETRY_VERSION ?= 1.6.0
PROJECT_NAME = photools

# Docker settings
DOCKER_REGISTRY ?= localhost:5000
IMAGE_TAG ?= latest
COMPOSE_FILE ?= docker-compose.yml

# AI Model settings
MODELS_DIR = ./models
DEFAULT_EMBEDDING_MODEL = sentence-transformers/all-MiniLM-L6-v2
DEFAULT_VISION_MODEL = microsoft/resnet-50

# Development settings
TEST_COMMAND = pytest -v --cov=src --cov-report=html --cov-report=term
LINT_COMMAND = ruff check src tests
FORMAT_COMMAND = black src tests && isort src tests

##@ Help
help: ## Display this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\n\033[1mUsage:\033[0m\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Setup and Installation
install: ## Install dependencies and setup development environment
	@echo "🔧 Setting up development environment..."
	@./scripts/check-dependencies.sh
	@if [ $? -ne 0 ]; then \
		echo "❌ Dependency check failed. Please fix the issues above."; \
		exit 1; \
	fi
	@echo "✅ Development environment ready!"

setup-env: ## Create .env file from template
	@if [ ! -f .env ]; then \
		echo "📝 Creating .env file from template..."; \
		cp .env.example .env; \
		echo "✅ Please edit .env with your configuration"; \
	else \
		echo "⚠️  .env file already exists"; \
	fi

##@ Poetry Dependency Management
deps-install: ## Install all Poetry dependencies
	@echo "📦 Installing Poetry dependencies..."
	@poetry install
	@echo "✅ Dependencies installed"

deps-install-minimal: ## Install only main dependencies (Stage 1: API Foundation)
	@echo "📦 Installing minimal dependencies (API foundation)..."
	@poetry install --only=main
	@echo "✅ Minimal dependencies installed"

deps-install-dev: ## Install main + development dependencies
	@echo "📦 Installing development dependencies..."
	@poetry install --with=dev
	@echo "✅ Development dependencies installed"

deps-install-test: ## Install main + development + testing dependencies
	@echo "📦 Installing testing dependencies..."
	@poetry install --with=dev,test
	@echo "✅ Testing dependencies installed"

deps-install-all: ## Install all dependency groups
	@echo "📦 Installing all dependencies..."
	@poetry install --with=dev,test,docs
	@echo "✅ All dependencies installed"

deps-add: ## Add a new dependency (usage: make deps-add PACKAGE=fastapi)
	@if [ -z "$(PACKAGE)" ]; then \
		echo "❌ Usage: make deps-add PACKAGE=package-name"; \
		echo "   Optional: GROUP=dev|test|docs (default: main)"; \
		exit 1; \
	fi
	@if [ -n "$(GROUP)" ]; then \
		echo "📦 Adding $(PACKAGE) to $(GROUP) group..."; \
		poetry add --group=$(GROUP) $(PACKAGE); \
	else \
		echo "📦 Adding $(PACKAGE) to main dependencies..."; \
		poetry add $(PACKAGE); \
	fi
	@echo "✅ $(PACKAGE) added successfully"

deps-remove: ## Remove a dependency (usage: make deps-remove PACKAGE=package-name)
	@if [ -z "$(PACKAGE)" ]; then \
		echo "❌ Usage: make deps-remove PACKAGE=package-name"; \
		echo "   Optional: GROUP=dev|test|docs"; \
		exit 1; \
	fi
	@if [ -n "$(GROUP)" ]; then \
		echo "📦 Removing $(PACKAGE) from $(GROUP) group..."; \
		poetry remove --group=$(GROUP) $(PACKAGE); \
	else \
		echo "📦 Removing $(PACKAGE) from dependencies..."; \
		poetry remove $(PACKAGE); \
	fi
	@echo "✅ $(PACKAGE) removed successfully"

deps-update: ## Update all dependencies
	@echo "📦 Updating all dependencies..."
	@poetry update
	@echo "✅ Dependencies updated"

deps-update-package: ## Update specific package (usage: make deps-update-package PACKAGE=fastapi)
	@if [ -z "$(PACKAGE)" ]; then \
		echo "❌ Usage: make deps-update-package PACKAGE=package-name"; \
		exit 1; \
	fi
	@echo "📦 Updating $(PACKAGE)..."
	@poetry update $(PACKAGE)
	@echo "✅ $(PACKAGE) updated"

deps-show: ## Show installed dependencies
	@echo "📦 Installed dependencies:"
	@poetry show

deps-show-tree: ## Show dependency tree
	@echo "📦 Dependency tree:"
	@poetry show --tree

deps-show-outdated: ## Show outdated dependencies
	@echo "📦 Checking for outdated dependencies..."
	@poetry show --outdated

deps-show-latest: ## Show latest versions of dependencies
	@echo "📦 Latest available versions:"
	@poetry show --latest

deps-lock: ## Generate/update poetry.lock file
	@echo "🔒 Updating lock file..."
	@poetry lock
	@echo "✅ Lock file updated"

deps-lock-check: ## Check if poetry.lock is up to date
	@echo "🔒 Checking lock file..."
	@poetry check --lock
	@echo "✅ Lock file is up to date"

deps-export: ## Export dependencies to requirements.txt
	@echo "📄 Exporting dependencies to requirements.txt..."
	@poetry export -f requirements.txt --output requirements.txt --without-hashes
	@poetry export -f requirements.txt --output requirements-dev.txt --with=dev --without-hashes
	@echo "✅ Requirements files generated"

deps-audit: ## Audit dependencies for security vulnerabilities
	@echo "🔍 Auditing dependencies for security issues..."
	@poetry show --tree
	@echo "⚠️  For comprehensive security audit, consider using 'safety check'"
	@echo "   Install with: poetry add --group=dev safety"
	@echo "   Run with: poetry run safety check"

deps-clean: ## Clean Poetry cache and reinstall
	@echo "🧹 Cleaning Poetry cache..."
	@poetry cache clear --all pypi
	@echo "📦 Reinstalling dependencies..."
	@poetry install
	@echo "✅ Dependencies cleaned and reinstalled"

deps-info: ## Show Poetry configuration and project info
	@echo "📋 Poetry configuration:"
	@poetry config --list
	@echo
	@echo "📋 Project info:"
	@poetry show --tree --only=main | head -20

##@ Staged Dependencies (Development Workflow)
stage1-deps: deps-install-minimal ## Stage 1: Install minimal API foundation dependencies
	@echo "🎯 Stage 1 complete: Basic FastAPI server ready"
	@echo "   You can now: build basic API endpoints, health checks"

# stage2-deps: ## Stage 2: Add file handling dependencies
# 	@echo "🎯 Stage 2: Adding file handling capabilities..."
# 	@$(MAKE) deps-add PACKAGE=python-multipart
# 	@$(MAKE) deps-add PACKAGE=pillow
# 	@$(MAKE) deps-add PACKAGE=aiofiles
# 	@$(MAKE) deps-add PACKAGE=pydantic-settings
# 	@echo "✅ Stage 2 complete: File upload and configuration ready"

# stage3-deps: ## Stage 3: Add database dependencies
# 	@echo "🎯 Stage 3: Adding database capabilities..."
# 	@$(MAKE) deps-add PACKAGE=sqlalchemy
# 	@$(MAKE) deps-add PACKAGE=alembic
# 	@$(MAKE) deps-add PACKAGE=psycopg2-binary
# 	@$(MAKE) deps-add PACKAGE=pytest-asyncio GROUP=dev
# 	@echo "✅ Stage 3 complete: Database integration ready"

# stage4-deps: ## Stage 4: Add AI model dependencies
# 	@echo "🎯 Stage 4: Adding AI model capabilities..."
# 	@$(MAKE) deps-add PACKAGE=transformers
# 	@$(MAKE) deps-add PACKAGE=sentence-transformers
# 	@$(MAKE) deps-add PACKAGE=torch
# 	@echo "✅ Stage 4 complete: AI model integration ready"

# stage5-deps: ## Stage 5: Add vector search dependencies
# 	@echo "🎯 Stage 5: Adding vector search capabilities..."
# 	@$(MAKE) deps-add PACKAGE=chromadb
# 	@echo "✅ Stage 5 complete: Semantic search ready"

# stage6-deps: ## Stage 6: Add background processing dependencies
# 	@echo "🎯 Stage 6: Adding background processing..."
# 	@$(MAKE) deps-add PACKAGE=celery
# 	@$(MAKE) deps-add PACKAGE=redis
# 	@echo "✅ Stage 6 complete: Background processing ready"

# stage7-deps: ## Stage 7: Add production dependencies
# 	@echo "🎯 Stage 7: Adding production features..."
# 	@$(MAKE) deps-add PACKAGE=prometheus-client
# 	@$(MAKE) deps-add PACKAGE=httpx
# 	@echo "✅ Stage 7 complete: Production monitoring ready"

# stage8-deps: ## Stage 8: Add comprehensive testing dependencies
# 	@echo "🎯 Stage 8: Adding advanced testing capabilities..."
# 	@$(MAKE) deps-add PACKAGE=mypy GROUP=dev
# 	@$(MAKE) deps-add PACKAGE=isort GROUP=dev
# 	@$(MAKE) deps-add PACKAGE=pre-commit GROUP=dev
# 	@$(MAKE) deps-add PACKAGE=pytest-cov GROUP=dev
# 	@$(MAKE) deps-add PACKAGE=testcontainers GROUP=test
# 	@$(MAKE) deps-add PACKAGE=factory-boy GROUP=test
# 	@echo "✅ Stage 8 complete: Comprehensive testing ready"

##@ Development Environment
env: ## Activate Poetry virtual environment
	@echo "🔧 Activating Poetry virtual environment..."
	@poetry env activate
	@echo "✅ Virtual environment activated"

dev: ## Start development servers with hot reload
	@echo "🚀 Starting development environment..."
	@docker compose -f $(COMPOSE_FILE) up -d postgres redis
	@sleep 3
	@poetry run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000 &
	@poetry run celery -A src.workers.celery_app worker --loglevel=info &
	@echo "✅ Development servers running:"
	@echo "   🌐 API: http://localhost:8000"
	@echo "   📊 API Docs: http://localhost:8000/docs"

dev-full: ## Start full development environment with all services
	@echo "🚀 Starting full development environment..."
	@docker compose -f $(COMPOSE_FILE) up -d
	@echo "✅ Full environment running - check docker compose logs"

stop: ## Stop all development services
	@echo "🛑 Stopping development servers..."
	@pkill -f "uvicorn src.api.main:app" || true
	@pkill -f "celery -A src.workers.celery_app" || true
	@docker compose -f $(COMPOSE_FILE) down
	@echo "✅ All services stopped"

restart: stop dev ## Restart development environment

logs: ## Show logs from all services
	@docker compose -f $(COMPOSE_FILE) logs -f

shell: ## Open interactive Python shell with project context
	@poetry run python -c "from src.config.settings import get_settings; print('🐍 Python shell ready with project context')"

##@ Testing and Quality
test: ## Run full test suite
	@echo "🧪 Running tests..."
	@poetry run $(TEST_COMMAND)

test-unit: ## Run unit tests only
	@echo "🧪 Running unit tests..."
	@poetry run pytest tests/unit/ -v

test-integration: ## Run integration tests only
	@echo "🧪 Running integration tests..."
	@poetry run pytest tests/integration/ -v

lint: ## Run code linting
	@echo "🔍 Linting code..."
	@poetry run $(LINT_COMMAND)

format: ## Format code with black and isort
	@echo "🎨 Formatting code..."
	@poetry run $(FORMAT_COMMAND)

type-check: ## Run type checking with mypy
	@echo "🔍 Type checking..."
	@poetry run mypy src/

quality: lint type-check ## Run all code quality checks

coverage: ## Generate coverage report
	@echo "📊 Generating coverage report..."
	@poetry run pytest --cov=src --cov-report=html --cov-report=term
	@echo "📊 Coverage report: htmlcov/index.html"

# ##@ AI Models and Data ## TODO - enable when AI features are implemented
# setup-models: ## Download and cache AI models locally
# 	@echo "🤖 Setting up AI models..."
# 	@mkdir -p $(MODELS_DIR)
# 	@poetry run python scripts/download-models.py \
# 		--embedding-model $(DEFAULT_EMBEDDING_MODEL) \
# 		--vision-model $(DEFAULT_VISION_MODEL) \
# 		--output-dir $(MODELS_DIR)
# 	@echo "✅ AI models cached locally"

# benchmark-models: ## Benchmark AI model performance
# 	@echo "⚡ Benchmarking AI models..."
# 	@poetry run python scripts/benchmark-models.py \
# 		--output benchmark-results.json
# 	@echo "✅ Benchmark complete: benchmark-results.json"

# test-routing: ## Test model routing decisions
# 	@echo "🧠 Testing model routing logic..."
# 	@poetry run python scripts/test-routing.py

# ##@ Database
# db-migrate: ## Create new database migration
# 	@echo "📝 Creating database migration..."
# 	@poetry run alembic revision --autogenerate -m "$(MESSAGE)"

# db-upgrade: ## Apply database migrations
# 	@echo "⬆️  Applying database migrations..."
# 	@poetry run alembic upgrade head

# db-downgrade: ## Rollback database migrations
# 	@echo "⬇️  Rolling back database migration..."
# 	@poetry run alembic downgrade -1

# db-reset: ## Reset database (⚠️  destructive)
# 	@echo "⚠️  Resetting database..."
# 	@read -p "Are you sure? This will delete all data [y/N]: " confirm && [ $$confirm = y ]
# 	@poetry run alembic downgrade base
# 	@poetry run alembic upgrade head
# 	@echo "✅ Database reset complete"

##@ Docker and Deployment
build: ## Build Docker images
	@echo "🐳 Building Docker images..."
	@docker build -f deployments/docker/Dockerfile.api -t $(PROJECT_NAME)-api:$(IMAGE_TAG) .
	@docker build -f deployments/docker/Dockerfile.worker -t $(PROJECT_NAME)-worker:$(IMAGE_TAG) .
	@echo "✅ Docker images built"

build-prod: ## Build production Docker images
	@echo "🐳 Building production images..."
	@docker compose -f docker compose.prod.yml build
	@echo "✅ Production images built"

deploy-local: build ## Deploy to local Docker environment
	@echo "🚀 Deploying locally..."
	@docker compose -f docker compose.prod.yml up -d
	@echo "✅ Local deployment complete"

##@ Maintenance
clean: ## Clean up generated files and caches
	@echo "🧹 Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf .pytest_cache htmlcov .coverage .mypy_cache
	@docker system prune -f
	@echo "✅ Cleanup complete"

check-health: ## Check health of all services
	@echo "🏥 Checking service health..."
	@curl -f http://localhost:8000/health || echo "❌ API unhealthy"
	@docker compose -f $(COMPOSE_FILE) ps

##@ Demo and Presentation
demo: ## Prepare demo environment with sample data
	@echo "🎬 Preparing demo environment..."
	@$(MAKE) clean
	@$(MAKE) install
	@$(MAKE) dev
	@echo "✅ Demo environment ready!"
	@echo "   🌐 Visit: http://localhost:8000"
	@echo "   📊 API Docs: http://localhost:8000/docs"

##@ Troubleshooting
debug: ## Show debug information
	@echo "📊 Environment Variables:"
	@echo "   PROJECT_NAME: ${PROJECT_NAME:-photools}"
	@echo "   API_PORT: ${API_PORT:-8000}"
	@echo "   POSTGRES_PORT: ${POSTGRES_PORT:-5432}"
	@echo "   REDIS_PORT: ${REDIS_PORT:-6379}"
	@echo ""
	@echo "📊 Poetry Status:"
	@poetry --version || echo "Poetry not installed locally"
	@echo ""
	@echo "📊 Docker Status:"
	@docker --version
	@docker compose version

debug-deps: ## Debug dependency issues
	@echo "🔍 Running dependency check in verbose mode..."
	@./scripts/check-dependencies.sh --verbose

debug-poetry: ## Debug Poetry configuration and dependencies
	@echo "🔍 Poetry debugging information:"
	@echo
	@echo "📋 Poetry version:"
	@poetry --version
	@echo
	@echo "📋 Poetry configuration:"
	@poetry config --list
	@echo
	@echo "📋 Virtual environment info:"
	@poetry env info
	@echo
	@echo "📋 Dependency tree:"
	@poetry show --tree
	@echo
	@echo "📋 Lock file status:"
	@poetry check --lock || echo "⚠️  Lock file may be outdated"

enable-scripts: ## Enable script files
	@echo "🔧 Enabling Script Permissions..."
	@chmod +x scripts/*.sh
	@echo "✅ Script Permissions Enabled"

fix-poetry: ## Fix common Poetry issues
	@echo "🔧 Fixing Poetry issues..."
	@echo "📦 Clearing Poetry cache..."
	@poetry cache clear --all pypi
	@echo "🔒 Regenerating lock file..."
	@poetry lock --no-update
	@echo "📦 Reinstalling dependencies..."
	@poetry install
	@echo "✅ Poetry issues fixed"







##@ Docker Development Workflow
docker-check: ## Check if Docker is running
	@echo "🐳 Checking Docker status..."
	@docker info >/dev/null 2>&1 || (echo "❌ Docker is not running. Please start Docker first." && exit 1)
	@echo "✅ Docker is running"

docker-build: docker-check ## Build development Docker images
	@echo "🔨 Building development Docker images..."
	@docker compose build
	@echo "✅ Docker images built successfully"

# docker-services: docker-check ## Start only infrastructure services (postgres, redis, chromadb)
# 	@echo "🚀 Starting infrastructure services..."
# 	@docker compose up -d postgres redis chromadb
# 	@echo "✅ Infrastructure services started"
# 	@echo "   📊 PostgreSQL: localhost:5432"
# 	@echo "   📊 Redis: localhost:6379" 
# 	@echo "   📊 ChromaDB: localhost:8900"

docker-dev: docker-check ## Start full development environment
	@echo "🚀 Starting full development environment..."
	@docker compose --profile app up -d
	@echo "✅ Development environment started"
	@echo "   🌐 API: http://localhost:8000"
	@echo "   📊 API Docs: http://localhost:8000/docs"

docker-dev-with-monitoring: docker-check ## Start development environment with monitoring tools
	@echo "🚀 Starting development environment with monitoring..."
	@docker compose --profile app --profile monitoring up -d
	@echo "✅ Development environment with monitoring started"
	@echo "   🌐 API: http://localhost:8000"
	@echo "   📊 API Docs: http://localhost:8000/docs"
	@echo "   🌸 Celery Flower: http://localhost:5555"
	@echo "   🐘 PgAdmin: http://localhost:8080"
	@echo "   📊 Redis Commander: http://localhost:8081"

docker-stop: ## Stop all Docker services
	@echo "🛑 Stopping all Docker services..."
	@docker compose down
	@echo "✅ All services stopped"

docker-restart: docker-stop docker-dev ## Restart development environment

docker-logs: ## Show logs from all services
	@docker compose logs -f

docker-logs-api: ## Show logs from API service only
	@docker compose logs -f api

docker-logs-worker: ## Show logs from worker service only
	@docker compose logs -f worker

docker-shell-api: ## Open shell in API container
	@docker compose exec api bash

docker-shell-postgres: ## Open psql shell in postgres container
	@docker compose exec postgres psql -U photo_user -d photo_catalog

docker-shell-redis: ## Open redis-cli shell in redis container
	@docker compose exec redis redis-cli

docker-clean: ## Clean up Docker resources
	@echo "🧹 Cleaning up Docker resources..."
	@docker compose down -v --remove-orphans
	@docker system prune -f
	@echo "✅ Docker cleanup complete"

docker-reset: docker-clean docker-build docker-dev ## Full reset: clean, rebuild, and start


##@ Database Management (Docker)
db-docker-migrate: ## Run database migrations in Docker
	@echo "📝 Running database migrations..."
	@docker compose exec api poetry run alembic upgrade head
	@echo "✅ Database migrations complete"

db-docker-reset: ## Reset database in Docker (⚠️  destructive)
	@echo "⚠️  Resetting database..."
	@read -p "Are you sure? This will delete all data [y/N]: " confirm && [ $$confirm = y ]
	@docker compose exec api poetry run alembic downgrade base
	@docker compose exec api poetry run alembic upgrade head
	@echo "✅ Database reset complete"


##@ Testing (Docker)
test-docker: ## Run tests in Docker environment
	@echo "🧪 Running tests in Docker..."
	@docker compose exec api poetry run pytest -v
	@echo "✅ Tests complete"

test-docker-coverage: ## Run tests with coverage in Docker
	@echo "🧪 Running tests with coverage in Docker..."
	@docker compose exec api poetry run pytest --cov=src --cov-report=html --cov-report=term
	@echo "✅ Tests with coverage complete"


##@ Quick Development Workflow
quick-start: setup-env docker-services ## Quick start: setup env and start services only
	@echo "🚀 Quick start complete!"
	@echo "   Now run: make dev (for local development)"
	@echo "   Or run: make docker-dev (for Docker development)"

full-start: setup-env docker-dev-with-monitoring deps-install ## Full start: everything needed for development
	@echo "🎉 Full development environment ready!"
	@echo "   🌐 API: http://localhost:8000"
	@echo "   📊 API Docs: http://localhost:8000/docs"
	@echo "   🌸 Celery Flower: http://localhost:5555"
	@echo "   🐘 PgAdmin: http://localhost:8080 (admin@photools.local / admin)"
	@echo "   📊 Redis Commander: http://localhost:8081"