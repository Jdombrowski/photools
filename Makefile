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
	@if [ $$? -ne 0 ]; then \
		echo "❌ Dependency check failed. Please fix the issues above."; \
		exit 1; \
	fi
	@echo "✅ Development environment ready!"

##@ Poetry Dependency Management
deps-install: ## Install all Poetry dependencies
	@echo "📦 Installing Poetry dependencies..."
	@poetry install
	@echo "✅ Dependencies installed"

setup-env: ## Create .env file from template
	@if [ ! -f .env ]; then \
		echo "📝 Creating .env file from template..."; \
		cp .env.example .env; \
		echo "✅ Please edit .env with your configuration"; \
	else \
		echo "⚠️  .env file already exists"; \
	fi

##@ Development
dev: ## Start development servers with hot reload
	@echo "🚀 Starting development environment..."
	@docker-compose -f $(COMPOSE_FILE) up -d postgres redis
	@sleep 3
	@poetry run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000 &
	@poetry run celery -A src.workers.celery_app worker --loglevel=info &
	@echo "✅ Development servers running:"
	@echo "   🌐 API: http://localhost:8000"
	@echo "   📊 API Docs: http://localhost:8000/docs"

dev-full: ## Start full development environment with all services
	@echo "🚀 Starting full development environment..."
	@docker-compose -f $(COMPOSE_FILE) up -d
	@echo "✅ Full environment running - check docker-compose logs"

stop: ## Stop all development services
	@echo "🛑 Stopping development servers..."
	@pkill -f "uvicorn src.api.main:app" || true
	@pkill -f "celery -A src.workers.celery_app" || true
	@docker-compose -f $(COMPOSE_FILE) down
	@echo "✅ All services stopped"

restart: stop dev ## Restart development environment

logs: ## Show logs from all services
	@docker-compose -f $(COMPOSE_FILE) logs -f

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

##@ AI Models and Data
setup-models: ## Download and cache AI models locally
	@echo "🤖 Setting up AI models..."
	@mkdir -p $(MODELS_DIR)
	@poetry run python scripts/download-models.py \
		--embedding-model $(DEFAULT_EMBEDDING_MODEL) \
		--vision-model $(DEFAULT_VISION_MODEL) \
		--output-dir $(MODELS_DIR)
	@echo "✅ AI models cached locally"

benchmark-models: ## Benchmark AI model performance
	@echo "⚡ Benchmarking AI models..."
	@poetry run python scripts/benchmark-models.py \
		--output benchmark-results.json
	@echo "✅ Benchmark complete: benchmark-results.json"

test-routing: ## Test model routing decisions
	@echo "🧠 Testing model routing logic..."
	@poetry run python scripts/test-routing.py

##@ Database
db-migrate: ## Create new database migration
	@echo "📝 Creating database migration..."
	@poetry run alembic revision --autogenerate -m "$(MESSAGE)"

db-upgrade: ## Apply database migrations
	@echo "⬆️  Applying database migrations..."
	@poetry run alembic upgrade head

db-downgrade: ## Rollback database migrations
	@echo "⬇️  Rolling back database migration..."
	@poetry run alembic downgrade -1

db-reset: ## Reset database (⚠️  destructive)
	@echo "⚠️  Resetting database..."
	@read -p "Are you sure? This will delete all data [y/N]: " confirm && [ $$confirm = y ]
	@poetry run alembic downgrade base
	@poetry run alembic upgrade head
	@echo "✅ Database reset complete"

##@ Docker and Deployment
build: ## Build Docker images
	@echo "🐳 Building Docker images..."
	@docker build -f deployments/docker/Dockerfile.api -t $(PROJECT_NAME)-api:$(IMAGE_TAG) .
	@docker build -f deployments/docker/Dockerfile.worker -t $(PROJECT_NAME)-worker:$(IMAGE_TAG) .
	@echo "✅ Docker images built"

build-prod: ## Build production Docker images
	@echo "🐳 Building production images..."
	@docker-compose -f docker-compose.prod.yml build
	@echo "✅ Production images built"

deploy-local: build ## Deploy to local Docker environment
	@echo "🚀 Deploying locally..."
	@docker-compose -f docker-compose.prod.yml up -d
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
	@docker-compose -f $(COMPOSE_FILE) ps

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
debug-deps: ## Debug dependency issues
	@echo "🔍 Running dependency check in verbose mode..."
	@./scripts/check-dependencies.sh --verbose

fix-permissions: ## Fix file permissions
	@echo "🔧 Fixing permissions..."
	@chmod +x scripts/*.sh
	@echo "✅ Permissions fixed"