# Google Docs Intelligent Merge - Skill Design

## Problem Statement

Current implementation does "smart append" - finding the right location but still dumping raw content. What we need is **true content synthesis**:

- **Analyze** document style, tone, purpose, and audience
- **Extract** key insights from meeting notes
- **Synthesize** information into document-appropriate format
- **Integrate** seamlessly into existing narrative
- **Preserve** document quality and professionalism

## Example: The Problem

### Current Document (Market Analysis section)
```
Market Analysis
The market for productivity applications is competitive, but there is a
clear demand for an app that combines simplicity with powerful features.
We aim to differentiate "AchieveIt" through superior user experience,
robust collaboration tools, and intelligent task management capabilities.
```

**Style:** Executive summary, concise, 3 sentences, high-level

### Meeting Notes (Raw)
```
📝 Meeting Notes — Customer Feedback on To-Do App
Date: October 31, 2025
Attendees: Product Manager: Sarah Lin, Customer: Alex Rivera

1. Purpose: To gather customer insights...
2. Customer's Current To-Do App Usage: App: Todoist (primary)...
3. Pain Points & Improvement Areas: Overwhelming task lists...
4. Desired Features & Suggestions: [table with 6 feature requests]
5. Product Manager Observations: Customer is power-user adjacent...
6. Next Steps: [3 action items with dates]
7. Summary: Alex's feedback highlights...
```

**Style:** Detailed meeting minutes, 3000+ characters, very granular

### ❌ Bad Integration (What We Were Doing)
Just insert the entire meeting notes:
```
Market Analysis
[existing 3 sentences]

## Customer Research & Feedback
📝 Meeting Notes — Customer Feedback on To-Do App
Date: October 31, 2025
[... entire 3000 character dump ...]
```

**Problems:**
- Style mismatch (executive vs detailed notes)
- Tone mismatch (polished vs raw notes)
- Length mismatch (3 sentences vs 3000 chars)
- Breaks document flow
- Not presentation-ready

### ✅ Good Integration (What We Should Do)

Synthesize insights and integrate naturally:

```
Market Analysis
The market for productivity applications is competitive, but there is a
clear demand for an app that combines simplicity with powerful features.
We aim to differentiate "AchieveIt" through superior user experience,
robust collaboration tools, and intelligent task management capabilities.

Recent customer research with power users validates this direction.
Key findings include strong demand for AI-assisted prioritization,
location-aware reminders, and enhanced collaboration features. Users
consistently cite "overwhelming task lists" and "lack of context" as
primary pain points with current solutions. These insights directly
inform our feature prioritization, particularly our focus mode and
contextual attachment capabilities.
```

**What Changed:**
- ✅ Extracted key insights (AI prioritization, location reminders, pain points)
- ✅ Matched tone (executive-level, not raw notes)
- ✅ Matched length (2 sentences added, not 3000 chars)
- ✅ Integrated naturally (flows from existing content)
- ✅ Presentation-ready (polished, professional)

## The Skill Workflow

### Phase 1: Analysis
```
Claude analyzes:
1. Document purpose (proposal, report, memo, etc.)
2. Target audience (executives, team, customers)
3. Style & tone (formal, casual, technical)
4. Current section content & length
5. Document structure & flow
```

### Phase 2: Extraction
```
Claude extracts from meeting notes:
1. Key insights relevant to target section
2. Important data points or metrics
3. Actionable conclusions
4. Supporting evidence
```

### Phase 3: Synthesis
```
Claude synthesizes:
1. Distills insights into executive summary level
2. Matches document tone and style
3. Maintains appropriate length ratio
4. Structures for natural flow
```

### Phase 4: Integration
```
Claude integrates:
1. Identifies exact insertion point
2. Adds transitional language
3. Ensures narrative continuity
4. Maintains document professionalism
```

### Phase 5: Attribution
```
Claude adds comment:
"Enhanced with insights from customer feedback session (Alex Rivera,
10/31/25). Full meeting notes available in [project folder/link]."
```

## Skill Instructions (SKILL.md format)

```markdown
# Google Docs Intelligent Merge

## When to Use
- User provides meeting notes, interview transcripts, or research to merge into a Google Doc
- Document needs to remain professional and presentation-ready
- Content should be synthesized, not dumped

## Core Principles

### 1. ANALYZE FIRST
Before touching the document:
- What is the document's purpose and audience?
- What is the current section's style, tone, and length?
- How formal/technical is the language?
- What is the narrative flow?

### 2. EXTRACT INSIGHTS
From the source material:
- What are the 3-5 KEY insights?
- What data/evidence supports the document's thesis?
- What conclusions are actionable?
- What can be safely omitted?

### 3. SYNTHESIZE, DON'T DUMP
Transform raw content:
- Match the document's tone (executive vs detailed)
- Match the document's style (formal vs casual)
- Match the section's length pattern
- Integrate, don't interrupt

### 4. QUALITY GATES
Before inserting:
- [ ] Would this section make sense to a manager/executive?
- [ ] Does it flow naturally from prior content?
- [ ] Is the length appropriate for the section?
- [ ] Is it presentation-ready?
- [ ] Would I be proud to send this to a client?

## Example Transformations

### Executive Summary Section
**Raw Notes:** [3 pages of detailed customer feedback]
**Synthesis:** "Recent customer research validates our approach. Users
consistently cite [key pain point] and express strong demand for [key
feature]. This directly informs our [strategic priority]." (2-3 sentences)

### Market Analysis Section
**Raw Notes:** [Meeting transcript with competitor discussion]
**Synthesis:** "Competitive analysis reveals [key finding] with primary
competitor [name] holding [stat]%. Our differentiation through [feature]
addresses a clear market gap." (2-3 sentences)

### Technical Specifications
**Raw Notes:** [Engineering meeting notes about architecture]
**Synthesis:** "System architecture utilizes [technology stack] to enable
[key capability]. Performance targets: [metric]. Scalability: [approach]."
(3-4 bullet points)

## Warning Signs

If you find yourself:
- ❌ Copying entire sections of notes
- ❌ Using note-taking language ("Attendees:", "Action Items:")
- ❌ Inserting content 3x longer than existing section
- ❌ Breaking the document's narrative flow
- ❌ Thinking "I'll just add it at the end"

STOP. Go back to synthesis step.

## The Test

Ask yourself: **"If my boss saw only this document (not the notes), would
they understand the insights and be able to make decisions?"**

If no → You're dumping notes, not synthesizing insights.
If yes → You're doing intelligent integration.
```

## Implementation Approach

### Option 1: Interactive Claude Code Workflow
```
User: "Merge these notes into the doc"
Claude:
  1. Reads document + notes
  2. Analyzes style/tone/audience
  3. Proposes synthesis (shows user):
     "I'll extract these 3 key insights and add 2 sentences
      to Market Analysis section that say: [preview]"
  4. User: "looks good" / "adjust this..."
  5. Claude: Executes synthesis and insertion
```

### Option 2: Skill with Clear Instructions
```markdown
The skill provides clear instructions:
- Always analyze before synthesizing
- Match document style/tone/length
- Extract insights, don't dump content
- Show preview before inserting
- Quality gate checklist
```

## Key Difference

**Old Approach:** "Where should I put this content?"
**New Approach:** "What insights should I extract and how should I present them?"

**Old Result:** Smart dumping
**New Result:** Professional integration

---

This is the difference between a junior employee who copies meeting notes
into a document, and a senior employee who extracts insights and maintains
document quality.
