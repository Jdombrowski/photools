# Architecture Decisions

This document logs key architectural decisions made during development to maintain consistency and provide context for future maintainers.

## Service Naming Convention

**Date**: 2025-07-26  
**Decision**: Use "Service" suffix for all service layer classes  
**Status**: Active

### Context

During refactoring, we considered removing the "Service" suffix from class names (e.g., `PhotoProcessorService` → `PhotoProcessorService`) to reduce verbosity.

### Decision

We decided to **keep the "Service" suffix** for all service layer components.

### Rationale

1. **Codebase Consistency**: Existing services already use this pattern:

   - `PhotoUploadService`
   - `PhotoImportService`
   - `SecureFileSystemService`

2. **Architectural Clarity**: The suffix makes the service layer explicit, which helps with:

   - Team onboarding
   - Domain-Driven Design (DDD) implementation
   - Clear separation of concerns

3. **Disambiguation**: Avoids confusion between service classes and other types:

   - Data models/entities
   - Pure functions
   - Value objects

4. **Industry Standards**: Aligns with common patterns in enterprise frameworks (Spring, ASP.NET)

### Examples

- ✅ `PhotoProcessorService`
- ✅ `PhotoUploadService`
- ✅ `PhotoImportService`
- ❌ `PhotoProcessorService`
- ❌ `PhotoUpload`

### Future Considerations

- All new service classes should follow this convention
- Consider renaming inconsistent classes like `SecureDirectoryScanner` → `DirectoryScannerService`
- This decision can be revisited if the codebase grows significantly and verbosity becomes a major issue

---

_Next decision: [Add new decisions above this line]_
