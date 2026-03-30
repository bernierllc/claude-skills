# Migration Plan: Block Insertion → Content Integration

## Executive Summary

**Current State:** Smart block insertion (finds where to put a blob of text)
**Target State:** Intelligent content integration (decomposes and integrates line-by-line)
**Timeline:** 4 phases over ~6-8 weeks
**Effort:** ~120-150 hours

**Key Insight:** We keep the document analysis infrastructure but completely rework the insertion logic.

---

## Phase Breakdown

### Phase 1: Foundation & Analysis (Week 1-2, ~30 hours)
Build content decomposition and semantic matching infrastructure.

### Phase 2: Integration Strategies (Week 3-4, ~40 hours)
Implement add/update/merge logic with exact location finding.

### Phase 3: Diff Preview & Execution (Week 5-6, ~30 hours)
Build diff generation and safe multi-change execution.

### Phase 4: Polish & Templates (Week 7-8, ~20 hours)
Add content type templates and refinements.

---

## Current System Analysis

### What We Have (Keep ✅)

**File: `smart_inserter.py`**

✅ **KEEP - Document Context Analysis** (Lines 68-166)
```python
def analyze_document_context(doc_url):
    # Analyzes sections, writing style, patterns
    # This is GOLD - reuse 100%
```
**Why:** Foundation for everything, works perfectly.

✅ **KEEP - Writing Style Detection** (Lines 168-225)
```python
def _analyze_writing_style(text, sections):
    # Detects tone, voice, tense, list preference
```
**Why:** Still needed for style matching during integration.

✅ **KEEP - Pattern Detection** (Lines 227-286)
```python
def _detect_content_patterns(doc, analysis):
    # Finds bullet lists, tables, section structures
```
**Why:** Helps determine how to format integrated content.

### What We Have (Rework 🔄)

🔄 **REWORK - Section Matching** (Lines 385-434)
```python
def _find_relevant_sections(sections, intent, target_section):
    # Currently: Find ONE section for block
    # Needed: Find MULTIPLE sections for different facts
```
**Changes:**
- Return multiple sections with confidence per fact
- Support fact-to-section mapping (not intent-to-section)

🔄 **REWORK - Insertion Strategy** (Lines 288-383)
```python
def determine_insertion_strategy(context, content, intent):
    # Currently: Where to put this block?
    # Needed: How to integrate each fact?
```
**Changes:**
- Accept decomposed facts instead of raw content
- Return integration strategies (add/update/merge) not insertion points
- Track exact locations for updates

### What We Have (Replace ❌)

❌ **REPLACE - Main API** (Lines 635-730)
```python
def smart_insert(doc_url, content, intent, auto_execute):
    # Too block-focused, needs complete rethink
```
**New:** `integrate_content()` with decomposition pipeline

❌ **REPLACE - Execution** (Lines 732-790)
```python
def _execute_strategy(doc_url, content, strategy, context):
    # Executes single block insertion
    # Needed: Execute multiple precise changes
```
**New:** `_execute_integration()` with diff tracking

---

## Detailed Migration Plan

## Phase 1: Foundation & Content Decomposition (Weeks 1-2)

### Goal
Add content decomposition layer that breaks content into semantic units.

### New Components

#### 1.1: Semantic Unit Data Structure (3 hours)

**File:** `scripts/semantic_units.py` (NEW)

```python
from dataclasses import dataclass
from typing import Literal, Optional

UnitType = Literal[
    'timeline', 'feature', 'decision', 'risk',
    'metric', 'action_item', 'team_assignment',
    'technical_detail', 'requirement'
]

@dataclass
class SemanticUnit:
    """A discrete piece of information from source content."""
    type: UnitType
    content: str
    priority: int  # 1-5
    source_line: int  # Which line in original content
    metadata: dict  # Additional context

@dataclass
class IntegrationAction:
    """How to integrate one semantic unit."""
    unit: SemanticUnit
    action: Literal['add', 'update', 'merge', 'skip']
    target_section: str
    target_index: int
    existing_content: Optional[str]  # For updates
    new_content: str
    confidence: float
    reasoning: str
```

**Tasks:**
- [ ] Create `semantic_units.py` with data structures
- [ ] Add validation and helper methods
- [ ] Write unit tests

**Deliverable:** Type-safe data structures for decomposition and integration.

---

#### 1.2: Content Decomposer (12 hours)

**File:** `scripts/content_decomposer.py` (NEW)

Since we can't actually call Claude API in Python, we'll use me (Claude) during execution. But the structure should support real API calls.

```python
class ContentDecomposer:
    """Decomposes content into semantic units."""

    def decompose(self, content: str, content_type: str) -> List[SemanticUnit]:
        """
        Main entry point.

        Args:
            content: Raw content (meeting notes, feature spec, etc.)
            content_type: Type hint ("meeting_notes", "feature_spec", etc.)

        Returns:
            List of SemanticUnit objects
        """

        if content_type == "meeting_notes":
            return self._decompose_meeting_notes(content)
        elif content_type == "feature_spec":
            return self._decompose_feature_spec(content)
        # etc.

    def _decompose_meeting_notes(self, content: str) -> List[SemanticUnit]:
        """
        Extract facts from meeting notes.

        Pattern recognition for:
        - Timeline dates → timeline units
        - Feature lists → feature units
        - Risk mentions → risk units
        - Decisions → decision units
        - Metrics → metric units
        - Action items → action_item units
        """

        units = []
        lines = content.split('\n')

        for i, line in enumerate(lines):
            # Pattern matching
            if self._is_timeline(line):
                units.append(SemanticUnit(
                    type='timeline',
                    content=self._extract_timeline(line),
                    priority=4,
                    source_line=i,
                    metadata={}
                ))
            elif self._is_feature(line):
                units.append(SemanticUnit(
                    type='feature',
                    content=self._extract_feature(line),
                    priority=3,
                    source_line=i,
                    metadata={}
                ))
            # etc.

        return units

    def _is_timeline(self, line: str) -> bool:
        """Detect if line contains timeline information."""
        # Look for date patterns, "Q1 2026", "March 15", etc.
        import re
        patterns = [
            r'Q\d \d{4}',  # Q1 2026
            r'\w+ \d{4}',  # March 2026
            r'\w+ \d{1,2}, \d{4}',  # March 15, 2026
            r'Phase \d+',  # Phase 1
        ]
        return any(re.search(p, line) for p in patterns)

    def _is_feature(self, line: str) -> bool:
        """Detect if line describes a feature."""
        # Look for feature indicators
        indicators = [
            'feature:', 'capability:', 'functionality:',
            '• ', '- ',  # Bullet points often list features
        ]
        return any(ind in line.lower() for ind in indicators)
```

**For POC:** Use pattern matching and heuristics.
**For Production:** Replace with Claude API calls.

**Tasks:**
- [ ] Create `ContentDecomposer` class
- [ ] Implement pattern matchers for 8+ unit types
- [ ] Add tests with real meeting notes
- [ ] Benchmark accuracy (target: >80% correct classification)

**Deliverable:** Working decomposer that extracts semantic units from content.

---

#### 1.3: Semantic Matcher (10 hours)

**File:** `scripts/semantic_matcher.py` (NEW)

```python
class SemanticMatcher:
    """Matches semantic units to document sections."""

    def find_target_sections(
        self,
        unit: SemanticUnit,
        document_sections: List[Dict]
    ) -> List[Tuple[Dict, float]]:
        """
        Find sections where this unit could be integrated.

        Returns:
            List of (section, confidence) tuples, sorted by confidence
        """

        matches = []

        for section in document_sections:
            score = self._calculate_match_score(unit, section)
            if score > 0.5:  # Threshold
                matches.append((section, score))

        # Sort by confidence
        matches.sort(key=lambda x: x[1], reverse=True)

        return matches

    def _calculate_match_score(
        self,
        unit: SemanticUnit,
        section: Dict
    ) -> float:
        """
        Calculate how well a unit matches a section.

        Uses:
        - Type-to-section mapping (timeline → roadmap)
        - Keyword overlap
        - Semantic similarity (in production: embeddings)
        """

        score = 0.0
        section_name = section.get('heading', '').lower()

        # Type-based matching
        type_section_map = {
            'timeline': ['roadmap', 'timeline', 'schedule', 'milestones'],
            'feature': ['features', 'functionality', 'capabilities'],
            'risk': ['risks', 'challenges', 'technical risks'],
            'metric': ['impact', 'metrics', 'business impact', 'roi'],
            'decision': ['decisions', 'outcomes', 'conclusions'],
            'team_assignment': ['team', 'roles', 'responsibilities'],
        }

        relevant_sections = type_section_map.get(unit.type, [])
        if any(rs in section_name for rs in relevant_sections):
            score += 0.6

        # Keyword overlap
        unit_keywords = set(unit.content.lower().split())
        section_keywords = set(section_name.split())
        overlap = len(unit_keywords & section_keywords)
        score += min(overlap * 0.1, 0.3)

        return min(score, 1.0)
```

**Tasks:**
- [ ] Create `SemanticMatcher` class
- [ ] Implement type-to-section mapping
- [ ] Add keyword overlap scoring
- [ ] Test with real documents
- [ ] Tune confidence thresholds

**Deliverable:** Matcher that finds relevant sections for each semantic unit.

---

#### 1.4: Update `SmartInserter` to use decomposition (5 hours)

**File:** `scripts/smart_inserter.py` (MODIFY)

Add new method:

```python
class SmartInserter:
    def __init__(self, editor):
        self.editor = editor
        self.decomposer = ContentDecomposer()  # NEW
        self.matcher = SemanticMatcher()  # NEW

    def analyze_content(
        self,
        content: str,
        content_type: str
    ) -> List[SemanticUnit]:
        """
        New method: Decompose content before integration.
        """
        return self.decomposer.decompose(content, content_type)
```

**Tasks:**
- [ ] Add decomposer and matcher as dependencies
- [ ] Add `analyze_content()` method
- [ ] Update imports
- [ ] Write integration tests

**Phase 1 Checkpoint:**
- ✅ Content decomposition working
- ✅ Semantic units extracted correctly
- ✅ Section matching functional
- ✅ Tests passing

---

## Phase 2: Integration Strategies (Weeks 3-4)

### Goal
Implement logic to determine how to integrate each unit (add/update/merge).

### New Components

#### 2.1: Existing Content Finder (12 hours)

**File:** `scripts/content_finder.py` (NEW)

```python
class ContentFinder:
    """Finds existing content in document that relates to semantic unit."""

    def find_related_content(
        self,
        doc: Dict,
        section: Dict,
        unit: SemanticUnit
    ) -> Optional[Dict]:
        """
        Search section for content related to this unit.

        Returns:
            {
                'type': 'exact_match' | 'partial_match' | 'semantic_match',
                'content': str,
                'start_index': int,
                'end_index': int,
                'confidence': float
            }
        """

        section_content = self._get_section_content(doc, section)

        # Exact match (duplicate)
        if unit.content.lower() in section_content.lower():
            return self._build_match('exact_match', ...)

        # Partial match (update needed)
        partial = self._find_partial_match(unit, section_content)
        if partial:
            return partial

        # Semantic match (merge opportunity)
        semantic = self._find_semantic_match(unit, section_content)
        if semantic:
            return semantic

        return None  # No existing content, will ADD

    def _find_partial_match(self, unit, content):
        """
        Find content that should be updated.

        Example:
        Unit: "Q1 2026 launch"
        Content: "Q2 2026: Initial release"
        → PARTIAL MATCH (update Q2 to Q1)
        """

        # For timeline units
        if unit.type == 'timeline':
            # Find existing timeline mentions
            import re
            timeline_pattern = r'Q\d \d{4}'
            matches = re.finditer(timeline_pattern, content)

            for match in matches:
                # Check if this is about the same thing
                if self._is_same_subject(unit.content, match.group()):
                    return self._build_match(
                        'partial_match',
                        content=match.group(),
                        start=match.start(),
                        end=match.end()
                    )

        # Similar logic for other types
        return None
```

**Tasks:**
- [ ] Create `ContentFinder` class
- [ ] Implement exact match detection
- [ ] Implement partial match (update detection)
- [ ] Implement semantic match (merge detection)
- [ ] Add tests for each match type

**Deliverable:** System that finds existing related content in document.

---

#### 2.2: Integration Strategy Determiner (15 hours)

**File:** `scripts/integration_strategy.py` (NEW)

```python
class StrategyDeterminer:
    """Determines how to integrate each semantic unit."""

    def __init__(self, editor):
        self.editor = editor
        self.finder = ContentFinder()

    def determine_strategy(
        self,
        doc: Dict,
        unit: SemanticUnit,
        target_sections: List[Tuple[Dict, float]]
    ) -> IntegrationAction:
        """
        Determine best integration strategy for one unit.

        Logic:
        1. Find existing related content in target sections
        2. Decide: add, update, merge, or skip
        3. Determine exact location
        4. Build IntegrationAction
        """

        # Use highest-confidence section
        section, confidence = target_sections[0]

        # Search for existing content
        existing = self.finder.find_related_content(doc, section, unit)

        # Determine action
        if existing is None:
            # No existing content → ADD
            return self._build_add_action(doc, section, unit, confidence)

        elif existing['type'] == 'exact_match':
            # Duplicate → SKIP
            return self._build_skip_action(unit, existing, confidence)

        elif existing['type'] == 'partial_match':
            # Outdated content → UPDATE
            return self._build_update_action(
                doc, section, unit, existing, confidence
            )

        elif existing['type'] == 'semantic_match':
            # Related content → MERGE
            return self._build_merge_action(
                doc, section, unit, existing, confidence
            )

    def _build_add_action(self, doc, section, unit, confidence):
        """Build action to add new content."""

        # Determine exact insertion point
        index = self._find_best_insertion_point(doc, section, unit)

        # Format content appropriately
        formatted_content = self._format_for_insertion(unit, section)

        return IntegrationAction(
            unit=unit,
            action='add',
            target_section=section['heading'],
            target_index=index,
            existing_content=None,
            new_content=formatted_content,
            confidence=confidence,
            reasoning=f"No existing content about {unit.type} found, adding new"
        )

    def _build_update_action(self, doc, section, unit, existing, confidence):
        """Build action to update existing content."""

        return IntegrationAction(
            unit=unit,
            action='update',
            target_section=section['heading'],
            target_index=existing['start_index'],
            existing_content=existing['content'],
            new_content=unit.content,
            confidence=confidence,
            reasoning=f"Found outdated {unit.type} content, updating"
        )

    def _find_best_insertion_point(self, doc, section, unit):
        """
        Find exact character index where content should be inserted.

        Strategy:
        - For features: After existing feature bullets
        - For timelines: In chronological order
        - For metrics: Near related metrics
        - Default: End of section
        """

        if unit.type == 'feature':
            # Insert after last bullet point
            return self._find_last_bullet_index(doc, section)

        elif unit.type == 'timeline':
            # Insert in chronological order
            return self._find_chronological_index(doc, section, unit)

        else:
            # Default: end of section
            return section.get('end_index', 0) - 1
```

**Tasks:**
- [ ] Create `StrategyDeterminer` class
- [ ] Implement add/update/merge/skip logic
- [ ] Implement smart insertion point finding
- [ ] Add content formatting for each unit type
- [ ] Write comprehensive tests

**Deliverable:** System that determines integration strategy for each unit.

---

#### 2.3: Update `SmartInserter` main API (8 hours)

**File:** `scripts/smart_inserter.py` (MODIFY)

Replace `smart_insert()` with `integrate_content()`:

```python
class SmartInserter:
    def __init__(self, editor):
        self.editor = editor
        self.decomposer = ContentDecomposer()
        self.matcher = SemanticMatcher()
        self.strategy_determiner = StrategyDeterminer(editor)  # NEW

    def integrate_content(
        self,
        doc_url: str,
        content: str,
        content_type: str,
        auto_execute: bool = False
    ) -> Dict[str, Any]:
        """
        NEW MAIN API: Integrate content line-by-line.

        Replaces: smart_insert()
        """

        # 1. Analyze document
        print("🔍 Analyzing document...")
        context = self.analyze_document_context(doc_url)
        doc = self.editor.get_document(doc_url, include_tabs_content=True)

        # 2. Decompose content
        print("📋 Decomposing content...")
        units = self.decomposer.decompose(content, content_type)
        print(f"   Found {len(units)} semantic units")

        # 3. For each unit, determine integration strategy
        print("🧠 Determining integration strategies...")
        actions = []

        for unit in units:
            # Find target sections
            target_sections = self.matcher.find_target_sections(
                unit,
                context.sections
            )

            if not target_sections:
                continue  # Skip if no good match

            # Determine how to integrate
            action = self.strategy_determiner.determine_strategy(
                doc,
                unit,
                target_sections
            )

            actions.append(action)

        # 4. Generate preview
        preview = self.generate_integration_preview(actions, context)

        # 5. Execute if approved
        result = {
            'success': True,
            'units': units,
            'actions': actions,
            'preview': preview,
            'executed': False
        }

        if auto_execute:
            exec_result = self.execute_integration(doc_url, actions)
            result['executed'] = True
            result['execution_result'] = exec_result

        return result
```

**Tasks:**
- [ ] Implement new `integrate_content()` method
- [ ] Wire up all components
- [ ] Add progress logging
- [ ] Maintain backward compatibility (keep old `smart_insert()` for now)

**Phase 2 Checkpoint:**
- ✅ Integration strategies working
- ✅ Add/Update/Merge/Skip logic correct
- ✅ Exact locations found
- ✅ End-to-end flow functional

---

## Phase 3: Diff Preview & Execution (Weeks 5-6)

### Goal
Show diff preview and execute multiple changes safely.

### New Components

#### 3.1: Diff Generator (10 hours)

**File:** `scripts/diff_generator.py` (NEW)

```python
class DiffGenerator:
    """Generates diff-style preview of integration changes."""

    def generate_preview(
        self,
        actions: List[IntegrationAction],
        context: DocumentContext
    ) -> str:
        """
        Generate visual diff preview.

        Returns:
            Multi-line string showing all changes grouped by section
        """

        # Group actions by section
        by_section = self._group_by_section(actions)

        lines = []
        lines.append("=" * 80)
        lines.append("INTEGRATION PREVIEW")
        lines.append("=" * 80)
        lines.append("")

        # Summary
        lines.append(f"Total Changes: {len(actions)}")
        lines.append(f"  • Add: {self._count_action(actions, 'add')}")
        lines.append(f"  • Update: {self._count_action(actions, 'update')}")
        lines.append(f"  • Merge: {self._count_action(actions, 'merge')}")
        lines.append(f"  • Skip: {self._count_action(actions, 'skip')}")
        lines.append("")

        # Changes by section
        for section_name, section_actions in by_section.items():
            lines.append("─" * 80)
            lines.append(f"Section: {section_name}")
            lines.append("─" * 80)
            lines.append("")

            for action in section_actions:
                if action.action == 'add':
                    lines.append(f"+ {action.new_content}")
                    lines.append(f"  (Add new {action.unit.type})")

                elif action.action == 'update':
                    lines.append(f"- {action.existing_content}")
                    lines.append(f"+ {action.new_content}")
                    lines.append(f"  (Update {action.unit.type})")

                elif action.action == 'merge':
                    lines.append(f"  {action.existing_content}")
                    lines.append(f"+ {action.new_content}")
                    lines.append(f"  (Merge {action.unit.type})")

                lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)
```

**Tasks:**
- [ ] Create `DiffGenerator` class
- [ ] Implement grouped diff generation
- [ ] Add color coding (if terminal supports)
- [ ] Add summary statistics
- [ ] Test with complex changes

**Deliverable:** Beautiful diff preview showing all changes.

---

#### 3.2: Safe Multi-Change Executor (12 hours)

**File:** `scripts/integration_executor.py` (NEW)

```python
class IntegrationExecutor:
    """Safely executes multiple integration actions."""

    def execute_integration(
        self,
        doc_url: str,
        actions: List[IntegrationAction]
    ) -> Dict[str, Any]:
        """
        Execute all integration actions in correct order.

        Challenge: Index shifting!
        - When you insert at index 100, all subsequent indices shift
        - Solution: Execute in reverse order (high index → low index)
        """

        doc_id = self.editor.extract_doc_id(doc_url)

        # Filter out skips
        executable = [a for a in actions if a.action != 'skip']

        # Sort by index (high to low) to avoid index shifting
        executable.sort(key=lambda a: a.target_index, reverse=True)

        # Build all requests
        requests = []
        for action in executable:
            if action.action == 'add':
                requests.extend(self._build_add_requests(action))
            elif action.action == 'update':
                requests.extend(self._build_update_requests(action))
            elif action.action == 'merge':
                requests.extend(self._build_merge_requests(action))

        # Execute all in one batchUpdate call
        try:
            self.editor._ensure_authenticated()
            result = self.editor.docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

            return {
                'success': True,
                'actions_executed': len(executable),
                'actions_skipped': len(actions) - len(executable)
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _build_add_requests(self, action: IntegrationAction):
        """Build Google Docs API requests for ADD action."""

        requests = []

        # Insert text
        requests.append({
            'insertText': {
                'location': {'index': action.target_index},
                'text': action.new_content
            }
        })

        # Apply blue color (new content)
        requests.append({
            'updateTextStyle': {
                'range': {
                    'startIndex': action.target_index,
                    'endIndex': action.target_index + len(action.new_content)
                },
                'textStyle': {
                    'foregroundColor': {
                        'color': {
                            'rgbColor': {'red': 0.0, 'green': 0.4, 'blue': 0.8}
                        }
                    }
                },
                'fields': 'foregroundColor'
            }
        })

        return requests

    def _build_update_requests(self, action: IntegrationAction):
        """Build Google Docs API requests for UPDATE action."""

        requests = []

        # Delete old content
        end_index = action.target_index + len(action.existing_content)
        requests.append({
            'deleteContentRange': {
                'range': {
                    'startIndex': action.target_index,
                    'endIndex': end_index
                }
            }
        })

        # Insert new content
        requests.append({
            'insertText': {
                'location': {'index': action.target_index},
                'text': action.new_content
            }
        })

        # Apply green color (updated content)
        requests.append({
            'updateTextStyle': {
                'range': {
                    'startIndex': action.target_index,
                    'endIndex': action.target_index + len(action.new_content)
                },
                'textStyle': {
                    'foregroundColor': {
                        'color': {
                            'rgbColor': {'red': 0.0, 'green': 0.6, 'blue': 0.0}
                        }
                    }
                },
                'fields': 'foregroundColor'
            }
        })

        return requests
```

**Tasks:**
- [ ] Create `IntegrationExecutor` class
- [ ] Implement safe index ordering
- [ ] Build requests for add/update/merge
- [ ] Add error handling and rollback
- [ ] Test with many simultaneous changes

**Deliverable:** Safe executor that handles multiple changes correctly.

---

#### 3.3: Wire up preview and execution (5 hours)

Update `SmartInserter` to use new components:

```python
class SmartInserter:
    def __init__(self, editor):
        # ... existing ...
        self.diff_generator = DiffGenerator()  # NEW
        self.executor = IntegrationExecutor(editor)  # NEW

    def generate_integration_preview(self, actions, context):
        """Use DiffGenerator."""
        return self.diff_generator.generate_preview(actions, context)

    def execute_integration(self, doc_url, actions):
        """Use IntegrationExecutor."""
        return self.executor.execute_integration(doc_url, actions)
```

**Phase 3 Checkpoint:**
- ✅ Diff preview looks great
- ✅ Multiple changes execute correctly
- ✅ Index shifting handled
- ✅ Color coding works

---

## Phase 4: Polish & Templates (Weeks 7-8)

### Goal
Add content type templates and refinements.

#### 4.1: Content Type Templates (8 hours)

**File:** `scripts/content_templates.py` (NEW)

```python
class ContentTemplate:
    """Template for specific content types."""

    def get_decomposition_patterns(self) -> Dict:
        """Return patterns for decomposing this content type."""
        pass

    def get_section_mapping(self) -> Dict:
        """Return unit type → section name mappings."""
        pass

class MeetingNotesTemplate(ContentTemplate):
    """Template for meeting notes."""

    def get_section_mapping(self):
        return {
            'timeline': ['Development Roadmap', 'Timeline', 'Schedule'],
            'feature': ['Core Features', 'Features', 'Functionality'],
            'decision': ['Decisions', 'Outcomes'],
            'metric': ['Business Impact', 'Metrics', 'ROI'],
            'risk': ['Technical Risks', 'Risks', 'Challenges'],
            'action_item': ['Next Steps', 'Action Items', 'Tasks'],
            'team_assignment': ['Team', 'Roles', 'Project Team']
        }

class FeatureSpecTemplate(ContentTemplate):
    """Template for feature specifications."""

    def get_section_mapping(self):
        return {
            'requirement': ['Requirements', 'Functional Requirements'],
            'technical_detail': ['Technical Architecture', 'Implementation'],
            'test': ['Testing', 'Test Plan', 'Quality Assurance'],
            'timeline': ['Timeline', 'Milestones']
        }
```

**Tasks:**
- [ ] Create template system
- [ ] Implement 5+ content type templates
- [ ] Wire into decomposer and matcher
- [ ] Test with each template

**Deliverable:** Template system for common content types.

---

#### 4.2: Refinements & Bug Fixes (6 hours)

- [ ] Handle edge cases (empty sections, malformed content)
- [ ] Improve error messages
- [ ] Add validation
- [ ] Performance optimization
- [ ] Documentation updates

#### 4.3: Demo & Examples (6 hours)

Update demo to show content integration:

**File:** `examples/demo_content_integration.py` (NEW)

```python
def demo_integration():
    """Show content integration vs block insertion."""

    smart = SmartInserter(editor)

    meeting_notes = """..."""

    result = smart.integrate_content(
        doc_url=doc_url,
        content=meeting_notes,
        content_type="meeting_notes",
        auto_execute=False
    )

    print(f"\n📋 Decomposed into {len(result['units'])} units:")
    for unit in result['units']:
        print(f"  • {unit.type}: {unit.content[:50]}...")

    print(f"\n🎯 Integration plan ({len(result['actions'])} actions):")
    print(result['preview'])
```

**Tasks:**
- [ ] Create comprehensive demo
- [ ] Add before/after examples
- [ ] Document all features
- [ ] Create tutorial

**Phase 4 Checkpoint:**
- ✅ Templates working
- ✅ All edge cases handled
- ✅ Demo looks amazing
- ✅ Documentation complete

---

## Migration Checklist

### Phase 1: Foundation ✅
- [ ] Create `semantic_units.py` with data structures
- [ ] Create `ContentDecomposer` class
- [ ] Implement 8+ unit type patterns
- [ ] Create `SemanticMatcher` class
- [ ] Update `SmartInserter` to use decomposition
- [ ] Write tests for all components
- [ ] **Deliverable:** Content decomposition working

### Phase 2: Strategies ✅
- [ ] Create `ContentFinder` class
- [ ] Implement match detection (exact/partial/semantic)
- [ ] Create `StrategyDeterminer` class
- [ ] Implement add/update/merge/skip logic
- [ ] Update `SmartInserter.integrate_content()` API
- [ ] Write comprehensive tests
- [ ] **Deliverable:** Integration strategies working

### Phase 3: Preview & Execute ✅
- [ ] Create `DiffGenerator` class
- [ ] Implement grouped diff preview
- [ ] Create `IntegrationExecutor` class
- [ ] Implement safe multi-change execution
- [ ] Wire up to `SmartInserter`
- [ ] Test with complex changes
- [ ] **Deliverable:** Diff preview and safe execution

### Phase 4: Polish ✅
- [ ] Create content type templates
- [ ] Handle edge cases
- [ ] Create demo and documentation
- [ ] Performance optimization
- [ ] **Deliverable:** Production-ready system

---

## Testing Strategy

### Unit Tests (Throughout)
- Test each component in isolation
- Mock dependencies
- Target: 80%+ coverage

### Integration Tests (Phase 2-3)
- Test full pipeline with real documents
- Verify correct decomposition → strategy → execution
- Test error handling

### End-to-End Tests (Phase 4)
- Real meeting notes → Real Google Doc
- Verify all changes applied correctly
- Performance benchmarks

---

## Success Metrics

### Quantitative
- **Decomposition Accuracy:** >80% correct unit classification
- **Section Matching:** >85% confidence on correct section
- **Integration Correctness:** >95% of actions execute as intended
- **Performance:** <10 seconds for typical meeting notes

### Qualitative
- **User Experience:** "This feels magical, not mechanical"
- **Preview Quality:** "I can see exactly what will change"
- **Accuracy:** "It integrated everything where I would have put it"

---

## Backward Compatibility

Keep `smart_insert()` method working during migration:

```python
class SmartInserter:
    def smart_insert(self, doc_url, content, intent, auto_execute=False):
        """
        DEPRECATED: Use integrate_content() instead.

        This method will be removed in version 2.0.
        """
        warnings.warn(
            "smart_insert() is deprecated, use integrate_content()",
            DeprecationWarning
        )

        # Fall back to old behavior
        # ... existing implementation ...
```

---

## Timeline Summary

| Phase | Weeks | Hours | Key Deliverable |
|-------|-------|-------|-----------------|
| Phase 1 | 1-2 | 30 | Content decomposition |
| Phase 2 | 3-4 | 40 | Integration strategies |
| Phase 3 | 5-6 | 30 | Diff preview & execution |
| Phase 4 | 7-8 | 20 | Polish & templates |
| **Total** | **8** | **120** | **Content Integration System** |

---

## Files Created/Modified

### New Files (8)
1. `scripts/semantic_units.py` - Data structures
2. `scripts/content_decomposer.py` - Content decomposition
3. `scripts/semantic_matcher.py` - Section matching
4. `scripts/content_finder.py` - Existing content finder
5. `scripts/integration_strategy.py` - Strategy determination
6. `scripts/diff_generator.py` - Diff preview
7. `scripts/integration_executor.py` - Safe execution
8. `scripts/content_templates.py` - Content type templates

### Modified Files (1)
1. `scripts/smart_inserter.py` - Main API refactor

### New Demos (1)
1. `examples/demo_content_integration.py` - Integration demo

---

## Risk Mitigation

**Risk:** Decomposition accuracy too low
**Mitigation:** Start with rule-based, iterate, eventually use Claude API

**Risk:** Integration strategies wrong
**Mitigation:** Extensive testing with real documents, preview before execution

**Risk:** Index shifting bugs
**Mitigation:** Thorough testing, sort by index, defensive programming

**Risk:** Timeline slippage
**Mitigation:** Incremental delivery, each phase functional on its own

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Allocate resources** (1 engineer, 8 weeks)
3. **Set up tracking** (GitHub project, weekly reviews)
4. **Begin Phase 1** (Week 1: Data structures and decomposer)

**Ready to start?** Phase 1 is well-defined and can begin immediately.
