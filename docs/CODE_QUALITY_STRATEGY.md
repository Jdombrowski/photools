# Code Quality Strategy: Ruff + Pylint Convergence

## Overview

This document outlines Photools' approach to code quality enforcement using a two-tier linting strategy that maximizes coverage while optimizing for development velocity.

## Strategy: Fast + Deep Analysis

### Core Principle
- **Ruff** (fast, comprehensive) handles all rules it can effectively cover
- **Pylint** (deep, analytical) focuses on complexity metrics and advanced static analysis
- **Zero overlap** - each tool handles distinct rule sets to avoid redundancy

## Tool Coverage Matrix

### Ruff Responsibilities (Primary Linter)
| Category | Rules | Rationale |
|----------|-------|-----------|
| **Code Style** | E, W (pycodestyle) | Fast, consistent formatting |
| **Imports** | I (isort), TID | Import organization and validation |
| **Syntax Errors** | F (pyflakes) | Basic syntax and name resolution |
| **Bug Prevention** | B (flake8-bugbear) | Common Python pitfalls |
| **Modern Python** | UP (pyupgrade) | Python version compatibility |
| **Type Annotations** | PYI, FA | Type hint validation |
| **Security** | S (bandit) | Security vulnerability detection |
| **Documentation** | D (pydocstyle) | Docstring conventions |
| **Complexity (Basic)** | C90 | McCabe complexity (basic) |
| **Performance** | PERF | Performance anti-patterns |

### Pylint Responsibilities (Deep Analysis)
| Category | Focus Areas | Rationale |
|----------|-------------|-----------|
| **Complexity Metrics** | Cyclomatic complexity, maintainability index | Deep code analysis |
| **Design Patterns** | Class design, inheritance issues | Architectural quality |
| **Data Flow** | Unused variables, unreachable code | Advanced static analysis |
| **Logic Errors** | Control flow issues, logical inconsistencies | Deep reasoning |
| **Module Structure** | Circular imports, coupling metrics | System-level analysis |
| **Custom Rules** | Domain-specific patterns | Project-specific quality |

## Configuration Strategy

### Ruff Configuration (pyproject.toml)
```toml
[tool.ruff]
line-length = 88
target-version = "py312"

# Comprehensive rule selection
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings  
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "UP",     # pyupgrade
    "C4",     # flake8-comprehensions
    "PYI",    # flake8-pyi
    "FA",     # flake8-future-annotations
    "S",      # flake8-bandit
    "D",      # pydocstyle
    "PERF",   # perflint
    "TID",    # flake8-tidy-imports
    "C90",    # mccabe (basic complexity)
]

# Ignore specific rules handled by pylint
ignore = [
    "D100",   # Missing docstring in public module (pylint handles)
    "D101",   # Missing docstring in public class (pylint handles)
    "D102",   # Missing docstring in public method (pylint handles)
    "C901",   # Complex function (pylint handles better)
]

# Per-file ignores
[tool.ruff.per-file-ignores]
"tests/*" = ["D", "S"]  # Relaxed docs and security for tests
"scripts/*" = ["D", "S101"]  # Relaxed for utility scripts
```

### Pylint Configuration (.pylintrc)
```ini
[MASTER]
disable=
    # Rules handled by ruff
    line-too-long,
    trailing-whitespace,
    missing-final-newline,
    unused-import,
    wrong-import-order,
    # Focus on complexity and design
    too-few-public-methods,
    
enable=
    # Complexity metrics
    cyclic-import,
    too-many-branches,
    too-many-statements,
    too-many-locals,
    too-many-arguments,
    # Design patterns  
    unused-variable,
    unused-argument,
    unreachable,
    # Logic errors
    undefined-variable,
    used-before-assignment,

[REPORTS]
output-format=colorized
reports=yes
score=yes

[REFACTORING]
max-nested-blocks=5

[DESIGN]
max-args=7
max-locals=15
max-branches=12
max-statements=50
max-attributes=10
max-public-methods=20
```

## Workflow Integration

### Development Workflow
```bash
# Fast feedback loop (pre-commit)
make lint-fast    # Ruff only (~100ms)

# Complete analysis (CI/review)
make lint-full    # Ruff + Pylint (~2-3s)

# Service-specific analysis
make lint-service SERVICE=photo_processor
```

### Make Target Strategy
```makefile
lint-fast: ## Fast linting with Ruff only
	@ruff check src tests --fix

lint-complexity: ## Deep analysis with Pylint
	@pylint src --reports=y --score=y

lint-full: lint-fast lint-complexity ## Complete linting suite

quality: lint-full type-check ## All quality checks
```

## Optimization Strategy

### Performance Targets
- **Ruff**: < 200ms for full codebase
- **Pylint**: < 5s for core modules only
- **Combined**: < 6s total for complete analysis

### Selective Pylint Usage
```bash
# Only run pylint on core business logic
pylint src/core/services/
pylint src/core/models/
# Skip infrastructure and API layers for speed
```

## Rule Convergence Plan

### Phase 1: Expand Ruff (Current)
- Add comprehensive rule sets to Ruff
- Maintain current speed (~100ms)
- Handle 80% of quality issues

### Phase 2: Add Targeted Pylint
- Focus on complexity metrics
- Core modules only
- Custom rules for domain patterns

### Phase 3: Optimize Performance
- Parallel execution where possible
- Caching strategies
- Incremental analysis

## Metrics and Monitoring

### Code Quality KPIs
- **Complexity Score**: Pylint complexity rating
- **Issue Density**: Issues per 1000 lines
- **Rule Coverage**: % of rules active
- **Performance**: Linting time per service

### Quality Gates
```bash
# CI Pipeline gates
ruff check --exit-zero src tests       # Must pass
pylint src/core --fail-under=8.0       # Minimum quality score
mypy src --strict                      # Type checking
```

## Error Handling Strategy

### Ruff Errors: Fail Fast
- Syntax errors, import issues, basic bugs
- **Action**: Block commits, fail CI

### Pylint Warnings: Inform and Improve
- Complexity metrics, design suggestions
- **Action**: Report in PR, track trends

## Implementation Checklist

- [ ] Expand Ruff configuration with comprehensive rules
- [ ] Add pylint with focused complexity configuration  
- [ ] Create `lint-fast` and `lint-complexity` make targets
- [ ] Integrate into pre-commit hooks (Ruff only)
- [ ] Add CI pipeline with both tools
- [ ] Document rule exceptions and rationale
- [ ] Create service-specific linting targets
- [ ] Implement performance monitoring
- [ ] Train team on two-tier approach

## Tool Versions and Compatibility

### Ruff
- **Version**: Latest stable (0.12.0+)
- **Update frequency**: Monthly
- **Compatibility**: Python 3.12+

### Pylint  
- **Version**: Latest stable (3.0+)
- **Update frequency**: Quarterly
- **Compatibility**: Python 3.12+

## Future Considerations

### Potential Additions
- **Mypy**: Type checking (already in use)
- **Bandit**: Security scanning (integrated in Ruff)
- **Vulture**: Dead code detection (if needed)
- **Radon**: Code metrics (if pylint insufficient)

### Tool Evolution
- Monitor Ruff development for new rule adoption
- Evaluate pylint alternatives (e.g., Prospector)
- Consider AST-based custom rules for domain patterns

## Conclusion

This two-tier approach maximizes code quality while maintaining developer velocity. Ruff handles the majority of issues with sub-second performance, while pylint provides deep insights into code complexity and design quality where it matters most.

The strategy is designed to evolve with the codebase and tooling ecosystem, ensuring sustainable code quality practices that scale with the project.