# Content Integration System - User Guide

## Overview

The Content Integration System transforms how content is added to Google Docs. Instead of dumping blocks of text, it intelligently integrates each piece of information into the right place with the right format.

## Quick Start

### Basic Usage

```python
from scripts.content_integrator import integrate_meeting_notes

# Simple meeting notes integration
result = integrate_meeting_notes(
    meeting_notes="""
    Meeting Notes — Product Planning

    Timeline:
    • Q1 2026: Launch analytics dashboard

    Decisions:
    ✓ Approved PostgreSQL as primary database

    Action Items:
    → Sarah to write tech spec by Friday
    """,
    document_sections=doc_sections,
    document_service=service,
    dry_run=False  # Set to True to preview without executing
)

print(f"✅ Applied {result.actions_executed} changes!")
```

### Full Control

```python
from scripts.content_integrator import ContentIntegrator

# Create integrator with full control
integrator = ContentIntegrator(
    document_service=service,
    show_preview=True,  # Show diff before executing
    dry_run=False       # Set True for preview-only mode
)

# Integrate any content type
result = integrator.integrate_content(
    content=my_content,
    document_sections=doc_sections,
    content_type='meeting_notes'  # or auto-detect
)
```

## Supported Content Types

The system supports 6 pre-configured content types:

### 1. Meeting Notes (`meeting_notes`)

**Best for:** Product meetings, standup notes, planning sessions

**Extracts:**
- Timeline items → Development Roadmap
- Features → Core Features
- Decisions → Decisions
- Action Items → Next Steps
- Team Assignments → Project Team
- Metrics → Business Impact
- Risks → Technical Risks

**Example:**
```
Meeting Notes — Sprint Planning

Timeline:
• Q1 2026: Beta release
• Phase 1 complete by March 15

Decisions:
✓ Approved microservices architecture
✓ Decided on React frontend

Action Items:
→ Kevin to finalize architecture diagram
→ Sarah to set up development environment

Team:
• Technical Lead: Kevin Patel
• Backend Lead: Sarah Chen
```

### 2. Feature Specs (`feature_spec`)

**Best for:** Detailed feature specifications, PRDs

**Extracts:**
- Requirements → Requirements
- Features → Features
- Technical Details → Technical Architecture
- Dependencies → Dependencies
- Metrics → Success Metrics

### 3. Sprint Planning (`sprint_planning`)

**Best for:** Sprint goals, backlog prioritization

**Extracts:**
- Sprint goals → Sprint Goals
- Tasks → Sprint Backlog
- Team capacity → Team Capacity
- Risks → Blockers

### 4. Technical Specs (`technical_spec`)

**Best for:** Architecture docs, implementation plans

**Extracts:**
- Architecture → Technical Design
- Requirements → Technical Requirements
- Dependencies → External Systems
- Decisions → Architectural Decisions

### 5. Roadmap Updates (`roadmap_update`)

**Best for:** Product roadmaps, release planning

**Extracts:**
- Timeline → Roadmap
- Features → Planned Features
- Metrics → Goals
- Dependencies → Prerequisites

### 6. Status Updates (`status_update`)

**Best for:** Weekly updates, progress reports

**Extracts:**
- Progress → Metrics/Status
- Blockers → Risks/Issues
- Action items → Next Steps
- Upcoming work → Timeline

## How It Works

### 1. Content Decomposition

The system breaks content into **semantic units** - individual facts that can be integrated separately:

```
Input: "Q1 2026: Analytics dashboard launch"
Output: SemanticUnit(type='timeline', content='Q1 2026: Analytics dashboard launch')
```

### 2. Semantic Matching

Each unit is matched to appropriate document sections:

```
timeline unit → "Development Roadmap" (80% confidence)
feature unit → "Core Features" (80% confidence)
decision unit → "Decisions" (80% confidence)
```

### 3. Integration Strategies

For each unit, the system determines the action:

- **ADD**: No existing content, add new
- **UPDATE**: Similar content exists, replace with newer version
- **MERGE**: Related content exists, combine them
- **SKIP**: Exact duplicate, no changes needed

### 4. Diff Preview

Before any changes, see exactly what will happen:

```
📄 Development Roadmap (2 changes)
   ➕ ADD timeline (72% confidence)
       ➕ • Q1 2026: Analytics dashboard launch

   🔄 UPDATE timeline (65% confidence)
       ➖ OLD: Phase 1: Foundation (Q4 2024)
       ➕ NEW: Phase 1: Core feature development (Dec 2024 - Feb 2025)
```

### 5. Safe Execution

Changes are applied in reverse order (highest index first) to prevent index shifting issues:

```
✅ 13 changes applied to 6 sections
   • Business Impact (2 changes)
   • Core Features (3 changes)
   • Development Roadmap (2 changes)
   • Next Steps (2 changes)
   • Project Team (2 changes)
   • Decisions (2 changes)
```

## API Reference

### ContentIntegrator

Main class for content integration.

#### Methods

**`integrate_content(content, document_sections, content_type=None)`**

Integrate content into document.

- **content** (str): Raw content to integrate
- **document_sections** (List[Dict]): Document structure
- **content_type** (str, optional): Content type or auto-detect
- **Returns**: IntegrationResult

**`preview_integration(content, document_sections, content_type=None)`**

Preview without executing.

- **Returns**: Preview string

**`get_integration_plan(content, document_sections, content_type=None)`**

Get structured plan for programmatic use.

- **Returns**: Plan dictionary

### Convenience Functions

**`integrate_meeting_notes(meeting_notes, document_sections, document_service, dry_run=False)`**

Quick integration for meeting notes (most common case).

**`preview_integration(content, document_sections, content_type=None)`**

Quick preview without execution.

**`get_integration_plan(content, document_sections, content_type=None)`**

Quick plan generation.

## Advanced Usage

### Custom Content Types

Auto-detection works well, but you can specify:

```python
result = integrator.integrate_content(
    content=my_content,
    document_sections=sections,
    content_type='technical_spec'  # Force specific type
)
```

### Preview Before Execution

Always preview first for important documents:

```python
# Step 1: Preview
integrator = ContentIntegrator(dry_run=True, show_preview=True)
integrator.integrate_content(content, sections)

# Step 2: If satisfied, execute
integrator = ContentIntegrator(dry_run=False, show_preview=False)
result = integrator.integrate_content(content, sections)
```

### Programmatic Integration

Get plan and decide programmatically:

```python
plan = get_integration_plan(content, sections)

print(f"Will make {plan['estimated_changes']} changes")
print(f"Confidence: {plan['strategies']['avg_confidence']:.0%}")

if plan['estimated_changes'] < 50 and plan['strategies']['avg_confidence'] > 0.7:
    # Proceed with integration
    result = integrate_meeting_notes(content, sections, service)
```

## Best Practices

### 1. Use Appropriate Content Types

- Meeting notes → `meeting_notes`
- Feature specs → `feature_spec`
- Architecture docs → `technical_spec`
- Status updates → `status_update`

### 2. Structure Your Content

Better input = better results:

**Good:**
```
Timeline:
• Q1 2026: Beta release
• Phase 1: Dec 2024 - Feb 2025

Decisions:
✓ Approved PostgreSQL
✓ Decided on microservices
```

**Poor:**
```
We decided in Q1 2026 to launch beta and use PostgreSQL maybe microservices
```

### 3. Always Preview First

For important documents:

```python
# Preview first
preview_integration(content, sections)

# Then execute
integrate_meeting_notes(content, sections, service)
```

### 4. Check Results

```python
result = integrate_meeting_notes(content, sections, service)

if result.success:
    print(f"✅ Success: {result.actions_executed} changes")
else:
    print(f"❌ Failed: {result.errors}")
```

## Troubleshooting

### Issue: No units extracted

**Cause:** Content doesn't match expected patterns

**Solution:** Add explicit markers:
```
Timeline:
• Q1 2026: Launch

Decisions:
✓ Approved feature X
```

### Issue: Wrong sections matched

**Cause:** Section names don't match expectations

**Solution:** Use standard section names:
- "Development Roadmap" not "Plans"
- "Core Features" not "What We're Building"
- "Next Steps" not "TODOs"

### Issue: Confidence too low

**Cause:** Ambiguous content or unclear section names

**Solution:**
1. Use clearer section headings
2. Structure content with markers
3. Specify content_type explicitly

## Migration from Old System

### Before (Block Insertion)

```python
# Old way: dump entire block
smart_insert(
    content=meeting_notes,
    document=doc
)
# Result: Entire meeting dumped in one section
```

### After (Content Integration)

```python
# New way: intelligent integration
integrate_meeting_notes(
    meeting_notes=meeting_notes,
    document_sections=doc_sections,
    document_service=service
)
# Result: 13 precise changes across 6 sections
```

## Performance

- **Decomposition**: ~0.001s for 100 words
- **Matching**: ~0.002s for 30 units
- **Strategy**: ~0.001s for 30 strategies
- **Execution**: ~0.1s per change (Google API)

**Total**: Typically <2s for meeting notes integration

## Support

For issues or questions:
1. Check test files in `examples/`
2. Review validation output
3. Enable `show_preview=True` for debugging

## Examples

See `examples/` directory for:
- `test_complete_pipeline.py` - Full pipeline demonstration
- `test_integration_strategies.py` - Strategy testing
- `test_semantic_matcher.py` - Matching validation
