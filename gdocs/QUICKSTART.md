# Google Docs Skill - Quick Start

## Installation Complete! ✅

The skill is now installed at: `~/.claude/skills/gdocs/`

## One-Time Setup (If Not Done Already)

### 1. OAuth Credentials Setup (~5-10 minutes)

```bash
cd /Users/mattbernier/projects/claude-skills/document-skills/gdocs
cat auth/oauth_setup.md
```

Follow the guide to:
1. Create Google Cloud project
2. Enable Google Docs API and Drive API
3. Download `credentials.json` to `auth/` directory

### 2. Authenticate

```bash
cd /Users/mattbernier/projects/claude-skills/document-skills/gdocs
python examples/test_auth.py
```

Browser will open for you to grant permissions. Tokens saved to `~/.claude-skills/gdocs/tokens.json`.

## Usage in Claude Conversations

### When User Provides Meeting Notes + Google Doc

**Your workflow:**

1. **Read both documents**
   ```python
   from scripts.gdocs_editor import GoogleDocsEditor

   editor = GoogleDocsEditor()
   doc_id = editor.extract_doc_id(doc_url)
   analysis = editor.analyze_document(doc_id)
   ```

2. **Analyze document** (in your mind/response)
   - Purpose: Proposal? Report? Memo?
   - Audience: Executives? Team? Customers?
   - Tone: Formal? Casual? Technical?
   - Section patterns: Concise vs detailed?

3. **Extract key insights** from meeting notes (3-5 max)
   - Not all details, just what matters
   - Data that supports document's thesis
   - Actionable conclusions

4. **Synthesize content** matching document style
   - Match tone and length pattern
   - No meeting-note artifacts
   - Presentation-ready

5. **Show preview to user**
   ```
   "I'll extract these 3 key insights and add 2-3 sentences to
   the Market Analysis section that say:

   [Preview synthesized content here]

   Should I proceed?"
   ```

6. **Execute after approval**
   ```python
   from scripts.content_inserter import ContentInserter, MergeOptions

   inserter = ContentInserter(editor)
   result = inserter.merge_content(
       doc_url=doc_url,
       content="[Your synthesized content]",
       section="Market Analysis",
       options=MergeOptions(
           preserve_comments=True,
           add_source_comment=True,
           add_inline_attribution=True,
           source_description="meeting on 10/31/25"
       )
   )
   ```

## What Gets Added

### In Document Text:
```
Recent customer research validates this approach and reveals
specific market opportunities. (from: customer feedback, 10/31/25)
                                ↑ italic purple text
```

### In Comments Panel:
```
📝 Added from customer feedback (10/31/25)

📍 Location: Paragraph #12
📝 Context: "...Recent customer research validates..."
```

## Quality Checklist

Before every insertion:
- [ ] Does content match document tone?
- [ ] Is length appropriate (not 10x longer)?
- [ ] Does it flow naturally?
- [ ] Is it presentation-ready?
- [ ] Would exec understand standalone?

## Common Patterns

### Executive Summary (3-4 sentences)
```
Input:  3,000+ char detailed notes
Output: 400-500 char executive summary
Style:  High-level, data-driven, formal
```

### Technical Spec (Bullet points)
```
Input:  Engineering discussion
Output: Structured key decisions
Style:  Technical but clear
```

### Status Report (Concise)
```
Input:  Team updates
Output: Progress summary
Style:  Factual, milestone-focused
```

## The Test

**Ask yourself:** "If boss saw only the document (not notes), could they make decisions?"

- **No** → You're dumping, not synthesizing
- **Yes** → You're doing it right!

## Examples

See `/Users/mattbernier/projects/claude-skills/document-skills/gdocs/`:
- `real_meeting_notes.txt` - Real customer feedback example
- `PHASE_5_PLAN.md` - Detailed synthesis documentation
- `SKILL_DESIGN.md` - Synthesis principles

## Support

Full documentation: `/Users/mattbernier/projects/claude-skills/document-skills/gdocs/README.md`

---

**Remember:** This skill is about **intelligent synthesis**, not insertion mechanics!
