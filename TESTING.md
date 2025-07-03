# Testing Guidelines

## Test Organization Philosophy

Using a **hybrid module-aligned** approach that prioritizes cohesion based on coupling:

### Guiding Principle: **"Tests live where their coupling is strongest"**

## Test Location Rules

### ✅ **Co-located with Module** (`src/module/component_test.py`)

- **Unit tests** for a single component
- **No external dependencies** beyond the component under test
- **High coupling** to implementation details
- **Microservice extraction ready** - travels with the code

**Examples:**

```
src/core/services/photo_processor_test.py     # Tests only PhotoProcessor
src/api/routes/filesystem_test.py             # Tests only filesystem routes
```

### ✅ **Module Integration Directory** (`src/module/tests/`)

- **Integration tests** within a module boundary
- Tests **multiple components** within the same module
- **Medium coupling** to module architecture
- Travels with module during microservice extraction

**Examples:**

```
src/core/tests/test_photo_pipeline.py         # Tests core service interactions
src/api/tests/test_route_integration.py       # Tests multiple API routes together
```

### ✅ **Shared Test Directory** (`tests/`)

- **Cross-module integration** and **system tests**
- **Shared test utilities** and **fixtures**
- **Test configuration** and **environment setup**
- **Low coupling** to specific implementations
- **High reusability** across modules

**Examples:**

```
tests/system/test_end_to_end.py               # Full system integration
tests/fixtures/                               # Shared test data
tests/utils/test_helpers.py                   # Reusable test utilities
tests/config/test_settings.py                 # Test environment management
```

## Decision Tree

When writing a test, ask:

1. **Does this test only exercise ONE component?**
   → Co-locate: `src/module/component_test.py`

2. **Does this test exercise MULTIPLE components in ONE module?**
   → Module integration: `src/module/tests/test_feature.py`

3. **Does this test cross module boundaries OR need shared utilities?**
   → Shared directory: `tests/category/test_feature.py`

## Naming Conventions

- **Co-located**: `component_test.py` (no "test_" prefix, clear it's a test by location)
- **Module integration**: `test_feature_name.py` (descriptive of what's being tested)
- **Shared tests**: `test_feature_name.py` (prefixed for discovery)

## Benefits

- **Microservice-ready**: Unit tests travel with their code
- **Clear ownership**: Teams own modules + their tests
- **Shared utilities**: Reusable across all modules
- **Discovery**: Clear rules eliminate ambiguity
- **Scalability**: Works for both monolith and microservices

## Migration Path

When extracting microservices:

1. Co-located tests move with the module ✅
2. Module integration tests move with the module ✅
3. Shared tests remain in the monolith for cross-service testing ✅
