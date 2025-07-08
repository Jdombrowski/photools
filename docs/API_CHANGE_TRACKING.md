# API Change Tracking for Startups

*A pragmatic guide to tracking API changes without over-engineering*

## The Problem

Startups face a unique challenge with API change tracking:
- **Too little** → No visibility into breaking changes, angry users, debugging hell
- **Too much** → Complex tooling overhead, ignored snapshots, high maintenance cost
- **Just right** → Simple, effective change detection with minimal effort

## The Spectrum of Solutions

### 1. **Nothing** (0% effort, 100% chaos)
```
❌ No change tracking
❌ No API documentation
❌ Breaking changes discovered in production
❌ "It worked yesterday" debugging
```

### 2. **Pact Tests** (100% effort, 100% accuracy)
```
✅ Contract-driven development
✅ Consumer-driven contracts
✅ Automated verification
❌ High setup and maintenance cost
❌ Requires consumer cooperation
❌ Complex for rapidly changing APIs
```

### 3. **Snapshot Tests** (20% effort, 80% effectiveness)
```
✅ Easy to implement
✅ Catches structural changes
✅ Good for stable APIs
❌ Brittle for dynamic data
❌ Often ignored when failing
❌ No semantic understanding
```

### 4. **The Startup Sweet Spot** (40% effort, 90% effectiveness)
```
✅ Automated but lightweight
✅ Focuses on breaking changes
✅ Easy to maintain
✅ Provides actionable insights
```

## Recommended Approach: Hybrid Lightweight Tracking

### Core Philosophy
- **Track structure, not data** - Schema changes matter more than content changes
- **Automate detection, manual review** - Let tools find changes, humans decide impact
- **Version-aware snapshots** - Link changes to releases for better debugging
- **Focus on breaking changes** - Not all changes are equal

### Implementation Strategy

#### 1. **Smart Snapshots** (Immediate - 2 hours)
```bash
# Generate schema-focused snapshots
make test-api-snapshot

# Compare with semantic understanding
make test-api-diff
```

**Benefits:**
- Catches structure changes in API responses
- Tied to development workflow via Makefile
- Easy to run before releases

**Makefile targets we just added:**
- `test-api` - Quick endpoint validation
- `test-api-verbose` - Full response inspection
- `test-api-snapshot` - Generate change detection snapshots
- `test-api-diff` - Compare current vs baseline

#### 2. **Schema Extraction** (Next Week - 4 hours)
```python
# Extract response schemas automatically
def extract_api_schema():
    schemas = {}
    for endpoint in API_ENDPOINTS:
        response = requests.get(endpoint)
        schemas[endpoint] = infer_schema(response.json())
    return schemas

# Track schema evolution
def compare_schemas(old, new):
    breaking_changes = []
    for endpoint, schema in new.items():
        if endpoint in old:
            changes = diff_schemas(old[endpoint], schema)
            breaking_changes.extend(filter_breaking_changes(changes))
    return breaking_changes
```

#### 3. **Automated Change Detection** (Next Sprint - 8 hours)
```bash
# Pre-commit hook
#!/bin/bash
# .git/hooks/pre-commit
if changes_detected_in_api_code; then
    echo "🔍 API code changed, checking for breaking changes..."
    make test-api-diff
    if has_breaking_changes; then
        echo "⚠️  Breaking changes detected. Review required."
        exit 1
    fi
fi
```

#### 4. **Release-Linked Documentation** (Month 2 - 12 hours)
```yaml
# .github/workflows/api-docs.yml
name: API Documentation
on:
  push:
    branches: [main]
    paths: ['src/api/**']
jobs:
  document-changes:
    runs-on: ubuntu-latest
    steps:
      - name: Generate API diff
        run: make test-api-diff
      - name: Update changelog
        run: ./scripts/update-api-changelog.sh
      - name: Create GitHub release notes
        if: github.event_name == 'push' && contains(github.ref, 'refs/tags/')
        run: gh release create ${{ github.ref_name }} --generate-notes
```

## Startup-Specific Patterns

### Pattern 1: **Progressive Enhancement**
Start simple, add complexity only when needed:

```bash
# Week 1: Basic snapshots
make test-api-snapshot

# Week 4: Schema validation
make test-api-schema-check

# Month 2: Automated reporting
make test-api-report

# Month 6: Consumer contract validation (if needed)
make test-api-contracts
```

### Pattern 2: **Developer-Friendly Tooling**
Make it easy to use, or it won't be used:

```bash
# Single command API testing
make test-api

# Pre-commit integration
git commit -m "feat: add photo upload"
# → Automatically checks for API changes
# → Generates diff if changes detected
# → Prompts for changelog update

# Release process
make release-prep
# → Runs full API test suite
# → Generates changelog
# → Creates migration guide if needed
```

### Pattern 3: **Semantic Change Detection**
Focus on what matters:

```python
# Not all changes are breaking
BREAKING_CHANGES = {
    'field_removed': 'high',
    'field_type_changed': 'high', 
    'required_field_added': 'high',
    'endpoint_removed': 'critical',
    'status_code_changed': 'medium',
    'field_added': 'low',  # Usually safe
    'field_renamed': 'medium',  # Depends on context
}
```

## Implementation Plan for Photools

### Phase 1: Foundation (This Week)
- [x] ✅ **Makefile API testing targets** - `test-api`, `test-api-verbose`, `test-api-snapshot`
- [ ] Test the new makefile targets with current API
- [ ] Document snapshot workflow in development process

### Phase 2: Schema Awareness (Next Week)
- [ ] Add JSON schema validation to API responses
- [ ] Create schema diff tool for breaking change detection
- [ ] Integrate with CI/CD pipeline

### Phase 3: Automation (Next Sprint)
- [ ] Pre-commit hooks for API change detection
- [ ] Automated changelog generation
- [ ] Release notes with API changes

### Phase 4: Advanced (Future)
- [ ] Consumer notification system
- [ ] Versioning strategy automation
- [ ] Performance regression detection

## Success Metrics

### Leading Indicators
- **Developer adoption** - Are devs running `make test-api` regularly?
- **Change detection rate** - Are we catching breaking changes before production?
- **Time to diagnosis** - How quickly can we identify the cause of API issues?

### Lagging Indicators
- **User-reported API issues** - Should decrease over time
- **Rollback frequency** - Fewer API-related rollbacks
- **Support ticket volume** - Less "it worked yesterday" issues

## Common Pitfalls to Avoid

### 1. **Snapshot Drift**
```bash
# Bad: Snapshots become stale
git commit -m "fix: update failing snapshot tests"

# Good: Understand why snapshots changed
make test-api-diff
# Review changes → Update snapshots consciously
make test-api-snapshot
```

### 2. **Over-Testing**
```bash
# Bad: Test everything
curl /api/v1/photos/123/metadata/exif/camera/lens/aperture/history

# Good: Test key integration points
curl /api/v1/photos/123
curl /api/v1/photos/123/preview
```

### 3. **Ignoring Failed Checks**
```bash
# Bad: Bypass checks when in a hurry
git commit -m "feat: urgent fix" --no-verify

# Good: Make checks fast and actionable
make test-api-quick  # < 10 seconds
```

## Tools and Technologies

### Free/Low-Cost Options
- **curl + jq** - CLI testing and JSON parsing
- **GitHub Actions** - CI/CD automation
- **Conventional Commits** - Semantic versioning
- **OpenAPI** - Schema documentation

### Paid Options (When Revenue Justifies)
- **Postman Monitoring** - API uptime and performance
- **Insomnia** - API development and testing
- **Pact Broker** - Contract testing infrastructure
- **Datadog** - APM and API monitoring

## Getting Started Today

1. **Test the new makefile targets:**
   ```bash
   make test-api
   make test-api-verbose
   make test-api-snapshot
   ```

2. **Integrate into development workflow:**
   ```bash
   # Before making API changes
   make test-api-snapshot
   
   # After making changes
   make test-api-diff
   ```

3. **Document your API change policy:**
   - When to bump major vs minor versions
   - How to communicate breaking changes
   - Review process for API modifications

## Conclusion

The key to startup API change tracking is **progressive enhancement**:
- Start with simple snapshots (today)
- Add schema validation (next week)
- Automate detection (next sprint)
- Scale up as needed (future)

The goal isn't perfect coverage—it's **actionable insight** with **minimal overhead**. Better to have simple tracking that you actually use than complex systems that get ignored under pressure.

---

*Remember: The best API change tracking system is the one your team actually uses consistently.*