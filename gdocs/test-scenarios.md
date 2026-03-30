# GDocs Skill Test Scenarios

## Purpose
Test scenarios to validate contextual insertion, formatting, color coding, and review capabilities.

## Scenario 1: Contextual Insertion After List

**Setup:**
- Document section "Market Challenges" with:
  - Opening paragraph
  - Bulleted list of 3 challenges
  - Closing paragraph

**Task:**
- Add research notes supporting the challenges

**Expected Failure (Baseline):**
- Agent dumps text at top of section
- Text doesn't fit naturally into section flow
- Should be added AFTER the list as "supporting evidence"

**Expected Success (After Fix):**
- Agent identifies list structure
- Adds content AFTER list with appropriate transition
- Formats as supporting paragraph or sub-section

## Scenario 2: Color Coding System

**Setup:**
- Document with existing content
- New content that contradicts some existing text

**Task:**
- Add new research that contradicts paragraph 3

**Expected Failure (Baseline):**
- No color coding applied
- New text is plain black
- No indication of what changed

**Expected Success (After Fix):**
- New text in BLUE
- Contradicted text in RED with STRIKETHROUGH
- Replacement text in GREEN next to red text
- Purple italic notes in parentheses explaining the change

## Scenario 3: Formatting Consistency

**Setup:**
- Executive document with:
  - 14pt Arial headers
  - 11pt Times body text
  - 1.15 line spacing
  - Specific bullet style

**Task:**
- Add content to existing section

**Expected Failure (Baseline):**
- Text uses default formatting
- Doesn't match document style
- Looks "dropped in"

**Expected Success (After Fix):**
- Text matches document fonts, sizes, spacing
- Bullet style matches if adding to list
- Looks professionally integrated

## Scenario 4: Review Step

**Setup:**
- Any document update

**Task:**
- Add content and verify what was added

**Expected Failure (Baseline):**
- No review of insertion
- Agent doesn't verify formatting or placement
- Moves on immediately after insertion

**Expected Success (After Fix):**
- Agent re-reads inserted content
- Verifies color coding applied correctly
- Checks formatting matches document
- Suggests improvements if needed

## Scenario 5: Document Improvement Suggestions

**Setup:**
- Document with:
  - Redundant sections
  - Inconsistent terminology
  - Poor flow between sections

**Task:**
- Add content to section 3

**Expected Failure (Baseline):**
- Agent only inserts content
- Doesn't notice document quality issues
- No improvement suggestions

**Expected Success (After Fix):**
- Agent notices redundancy between sections 2 and 3
- Suggests consolidation
- Points out terminology inconsistency
- Recommends flow improvements

## Testing Approach

### RED Phase (Baseline)
1. Launch subagent WITHOUT updated skill
2. Provide each scenario
3. Document exact behavior and rationalizations
4. Capture specific failures

### GREEN Phase (With Updates)
1. Update skill with:
   - Contextual insertion guidance
   - Full color coding system
   - Review step requirements
   - Improvement suggestion prompts
2. Re-test all scenarios
3. Verify compliance

### REFACTOR Phase
1. Identify any new rationalizations
2. Add explicit counters
3. Close loopholes
4. Re-test until bulletproof

## Pressure Types to Apply

1. **Time Pressure**: "I need this done quickly"
2. **Sunk Cost**: "I've already spent 2 hours on this doc"
3. **Authority**: "My boss needs this in 15 minutes"
4. **Exhaustion**: "This is the 10th document today"
5. **Complexity**: Multi-tab document with tables and lists

## Success Criteria

**Agent must:**
- [ ] Analyze section structure before inserting
- [ ] Place content contextually (not just at top)
- [ ] Apply full color coding system
- [ ] Review insertions for quality
- [ ] Suggest document improvements
- [ ] Maintain professional standards under ALL pressures
