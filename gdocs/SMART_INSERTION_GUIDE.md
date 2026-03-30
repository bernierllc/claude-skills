# Smart AI-Powered Content Insertion Guide

## Quick Start

```python
from scripts.gdocs_editor import GoogleDocsEditor
from scripts.smart_inserter import SmartInserter

# Initialize
editor = GoogleDocsEditor()
smart = SmartInserter(editor)

# Smart insert with preview (recommended)
result = smart.smart_insert(
    doc_url="https://docs.google.com/document/d/YOUR_DOC_ID/edit",
    content="Your content here...",
    intent="security feature",  # What is this content?
    auto_execute=False  # Show preview first
)

# Review the recommendation
if result['success']:
    strategy = result['recommended']
    print(f"Will insert into: {strategy.section_name}")
    print(f"Confidence: {strategy.confidence:.0%}")
    print(strategy.preview)

    # If you like it, execute manually
    # (or set auto_execute=True above)
```

## What It Does

### 1. **Document Analysis**
Analyzes your document to understand:
- **Sections**: All headings and their boundaries
- **Writing Style**: Tone (formal/casual), voice (1st/3rd person), tense
- **Content Patterns**: Bullet lists, numbered lists, tables
- **Document Structure**: How sections are organized

### 2. **Semantic Section Matching**
Instead of string matching section names, it understands **meaning**:

```python
Content: "Cerberus brute force protection"
Intent: "security feature"

Basic:  "Insert at end of document"
Smart:  "Authentication & Security (90% confidence)"
        "Core Features (80% confidence)"
```

### 3. **Style Matching**
Adjusts content to match your document's style:

```python
# Document is formal, third person
Original: "We'll implement Cerberus to bite hackers"
Adjusted: "The system implements Cerberus brute force protection"

# Document is casual, first person
Original: "The system implements advanced detection"
Adjusted: "We implement advanced threat detection"
```

### 4. **Format Detection**
Chooses the right format based on patterns:

- **Bullet list** if document uses bullets extensively
- **Numbered list** if content is sequential steps
- **Paragraph** for longer descriptive content

### 5. **Confidence Scoring**
Tells you how confident it is:

- **>80%**: High confidence, safe to auto-execute
- **60-80%**: Good confidence, review preview
- **<60%**: Low confidence, consider alternatives

### 6. **Preview Before Insertion**
Shows you exactly what will happen:

```
Preview of insertion in 'Authentication & Security':

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ...existing content in Authentication & Security...

   Cerberus Brute Force Protection: [your content]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Usage Examples

### Example 1: Add Feature Description

```python
smart.smart_insert(
    doc_url="...",
    content="Real-time collaboration with live cursors",
    intent="feature description",
    auto_execute=True  # High confidence, go ahead
)

# Result: Inserted into "Core Features & Functionality"
```

### Example 2: Add Security Measure

```python
result = smart.smart_insert(
    doc_url="...",
    content="Rate limiting at API gateway level",
    intent="security implementation",
    target_section="Authentication & Security",  # Suggest a section
    auto_execute=False  # Review first
)

# Review options
for strategy in result['strategies']:
    print(f"{strategy.section_name}: {strategy.confidence:.0%}")

# Execute if satisfied
if result['recommended'].confidence > 0.8:
    # Execute the strategy...
```

### Example 3: Add Meeting Notes

```python
smart.smart_insert(
    doc_url="...",
    content="""
Meeting Notes - Q1 Planning
Date: Jan 15, 2025
Attendees: Team leads

Key Decisions:
- Launch delayed to Feb 1
- Added feature X to roadmap
- Budget approved
    """,
    intent="meeting notes",
    auto_execute=False
)

# Smart system will:
# 1. Find "Meeting Notes" or "Project Updates" section
# 2. Format with proper spacing
# 3. Match document tone
# 4. Show preview
```

### Example 4: Multiple Strategies

```python
result = smart.smart_insert(
    doc_url="...",
    content="User onboarding flow improvements",
    intent="UX enhancement"
)

# Might suggest:
# 1. "User Experience Design" (85% confidence)
# 2. "Core Features" (75% confidence)
# 3. "Future Enhancements" (65% confidence)

# Choose which one to use
strategy = result['strategies'][1]  # Use 2nd option
# ... execute that strategy
```

## Intent Keywords

The `intent` parameter helps smart matching. Good examples:

**Features:**
- `"feature description"`
- `"new capability"`
- `"functionality"`

**Security:**
- `"security feature"`
- `"security implementation"`
- `"authentication"`

**Technical:**
- `"technical implementation"`
- `"architecture"`
- `"API endpoint"`

**Documentation:**
- `"meeting notes"`
- `"project update"`
- `"specification"`

**UX:**
- `"user experience"`
- `"design decision"`
- `"UI component"`

## Advanced: Custom Strategy Execution

```python
# Get strategies
result = smart.smart_insert(
    doc_url=doc_url,
    content=content,
    intent=intent,
    auto_execute=False
)

# Manually choose a strategy
chosen = result['strategies'][1]  # 2nd option

# Execute it manually
from scripts.smart_inserter import SmartInserter
smart._execute_strategy(
    doc_url=doc_url,
    content=content,
    strategy=chosen,
    context=result['context']
)
```

## Comparison: Basic vs Smart

### Basic Insertion (Old Way)
```python
from scripts.content_inserter import ContentInserter

inserter = ContentInserter(editor)
inserter.merge_content(
    doc_url=doc_url,
    content=content,
    section="Authentication & Security",  # Manual
    options=MergeOptions(...)
)
```

**Problems:**
- ❌ Must manually specify section name
- ❌ No style matching
- ❌ No confidence scoring
- ❌ No preview
- ❌ No alternatives
- ❌ Bugs with tab IDs and insertion indices

### Smart Insertion (New Way)
```python
from scripts.smart_inserter import SmartInserter

smart = SmartInserter(editor)
smart.smart_insert(
    doc_url=doc_url,
    content=content,
    intent="security feature",  # High-level intent
    auto_execute=False
)
```

**Benefits:**
- ✅ Automatic section discovery
- ✅ Style matching (tone, voice, tense)
- ✅ Confidence scoring
- ✅ Preview before execution
- ✅ Multiple strategy options
- ✅ Semantic understanding

## Future Enhancements

### Phase 2: Real AI Integration
Currently uses rule-based heuristics. Future: integrate Claude API for true AI reasoning:

```python
# Future implementation
strategy = claude_api.analyze(
    """
    Document sections: {sections}
    Content to insert: {content}
    Intent: {intent}

    Determine:
    1. Best section (with reasoning)
    2. Optimal format
    3. Style adjustments needed
    4. Confidence score
    """
)
```

### Phase 3: Multi-Section Updates
```python
smart.multi_section_update(
    doc_url=doc_url,
    feature="Cerberus brute force protection",
    update_related_sections=True
)

# Automatically updates:
# - Authentication & Security (implementation)
# - Core Features (user-facing description)
# - Technical Architecture (system design)
# - API Specs (rate limit endpoints)
```

### Phase 4: Template System
```python
smart.smart_insert_from_template(
    doc_url=doc_url,
    template="security_feature",
    data={
        'name': 'Cerberus',
        'purpose': 'Brute force protection',
        'implementation': 'Rate limiting + visual deterrent'
    }
)
```

## Troubleshooting

**Low Confidence (<60%)**
- Problem: Can't find good section match
- Solution: Use `target_section` to suggest a section
- Or: Check if document has clear section headings

**Wrong Style Adjustments**
- Problem: Style detection is incorrect
- Solution: Currently uses heuristics, will improve with real AI

**Multiple High-Confidence Options**
- Problem: 2+ sections seem equally good
- Solution: Review all strategies, choose based on context
- Or: Ask user which section to use

## Questions?

See examples in:
- `examples/demo_smart_insert.py` - Full demo
- `scripts/smart_inserter.py` - Implementation
- `SMART_INSERTION_GUIDE.md` - This guide
