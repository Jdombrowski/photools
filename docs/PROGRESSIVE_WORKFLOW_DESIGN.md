# Progressive Workflow Design - Photools

## Problem Statement

Most photo editors are built for individual photo perfection rather than efficient bulk processing and curation. They create file bloat with sidecar files, have poor batch operation UX, and lack clear at-a-glance understanding of processing stages.

## Design Goals

1. **Clear Stage Visibility**: Immediate understanding of where each photo is in the processing pipeline
2. **Progressive Filtering**: Efficiently trim large imports down to final selections
3. **Ergonomic Batch Operations**: Easy application of edits to similar photos
4. **Cross-App Portability**: Move photos between editing applications without loss
5. **Resource Efficiency**: Don't waste processing power on unusable media

## Proposed Architecture

### 7-Stage Processing Pipeline (V2)

```python
class ProcessingStage(Enum):
    INCOMING = "incoming"           # Just imported, needs first review
    REVIEWED = "reviewed"           # Quick preview done, kept/rejected
    BASIC_EDIT = "basic_edit"       # Exposure/basic corrections applied  
    CURATED = "curated"            # Selected as "good enough to work on"
    REFINED = "refined"            # Detailed editing in progress
    FINAL = "final"                # Ready for delivery/export
    REJECTED = "rejected"          # Marked for deletion/archive
```

### Database Schema

**Core Photo Model** (Extended with V2 fields):
```python
class Photo(Base):
    # V1: Basic file tracking
    file_path = Column(String, nullable=False, unique=True, index=True)
    file_hash = Column(String, nullable=False, index=True)
    processing_status = Column(String, default="pending")
    
    # V2: Progressive workflow fields
    processing_stage = Column(String, default="incoming")
    priority_level = Column(Integer, default=0)  # 0=normal, 1=good, 2=excellent
    needs_attention = Column(Boolean, default=True, index=True)
```

**Processing Action Tracking**:
```python
class ProcessingAction(Base):
    photo_id = Column(String, ForeignKey("photos.id"))
    stage_from = Column(String)
    stage_to = Column(String)
    action_type = Column(String)  # "basic_exposure", "crop", "color_grade"
    parameters = Column(JSON)     # Non-destructive edit parameters
    app_used = Column(String)     # "photools", "lightroom", etc.
    batch_id = Column(String)     # Group related actions
```

## Ideal Workflow

1. **Import** → Photos enter `INCOMING` stage
2. **Quick Preview** → Rapid review, advance to `REVIEWED` or `REJECTED`
3. **Basic Edits** → Batch exposure/color correction → `BASIC_EDIT`
4. **Curation** → Select best shots → `CURATED`
5. **Detailed Work** → Individual attention → `REFINED`
6. **Export** → Final outputs → `FINAL`

## File Organization Strategy

**Option A: Stage-Based Folders**
```
/photos/
├── incoming/           # Auto-import destination
├── reviewed/          # Passed first cut
├── curated/          # Worth editing
├── final/            # Completed work
└── rejected/         # Keep briefly, then delete
```

**Option B: Database-Only Stages** (Recommended)
```
/photos/2024/01/15/   # All photos stay in date folders
                      # Database handles stage filtering
                      # Cleaner for backup/organization
```

## UI/UX Concepts

### Dashboard View
```
┌─ INCOMING (1,247) ──────────────────────────┐
│ [●●●●●○○○○○] 50% reviewed                   │
│ Next: Quick preview batch (200 photos)      │
└─────────────────────────────────────────────┘

┌─ REVIEWED (623) ────────────────────────────┐  
│ [●●●○○○○○○○] 30% basic edits applied        │
│ Action: Batch exposure correction            │
└─────────────────────────────────────────────┘

┌─ CURATED (89) ──────────────────────────────┐
│ Ready for detailed editing                   │
│ Send to: [Lightroom] [Photoshop] [Other]   │
└─────────────────────────────────────────────┘
```

### Batch Operations API
```python
# Efficient workflow endpoints
POST /api/photos/batch-advance-stage
POST /api/photos/batch-apply-preset  
POST /api/photos/batch-export-to-app
GET  /api/photos/stage/{stage}?needs_attention=true
```

## Key Features

1. **Progressive Disclosure**
   - Only load basic metadata initially
   - Generate previews on-demand
   - Skip heavy processing for rejected photos

2. **Batch Intelligence**
   - Auto-group similar shots (time/location clusters)
   - Suggest batch operations based on patterns
   - One-click "apply to similar" functionality

3. **Inter-App Portability**
   - Export selection with XMP sidecars when needed
   - Import processing history from other apps
   - Generate manifests for folder handoffs

4. **Ergonomic Navigation**
   - Keyboard shortcuts for rapid curation
   - Visual progress indicators
   - "What needs attention next?" suggestions

## Implementation Plan

**V1 (Current)**:
- Basic photo import and metadata extraction
- Database foundation with V2 schema ready
- Simple processing status tracking

**V2 (Future)**:
- Full 7-stage pipeline implementation
- Dashboard with stage visualization
- Batch operation workflows
- Cross-app export/import

## Design Decisions

- **Database-driven stages** vs file-system organization (better for existing folder structures)
- **Non-destructive edits** stored as JSON parameters
- **Immutable originals** - never modify source files
- **Export-on-demand** approach to avoid file bloat