#!/usr/bin/env python3
"""
Example: Merge meeting notes into a Google Doc.

This demonstrates the primary use case for the Google Docs skill:
taking notes from a meeting and merging them into an existing document
while preserving all comments and formatting.

Usage:
    python examples/merge_meeting_notes.py <doc_url>

Example:
    python examples/merge_meeting_notes.py https://docs.google.com/document/d/ABC123/edit
"""

import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.content_inserter import ContentInserter, MergeOptions


def main():
    if len(sys.argv) < 2:
        print("Usage: python merge_meeting_notes.py <doc_url>")
        print("\nExample:")
        print("  python merge_meeting_notes.py https://docs.google.com/document/d/ABC123/edit")
        sys.exit(1)

    doc_url = sys.argv[1]

    # Sample meeting notes
    today = datetime.now().strftime('%Y-%m-%d')
    meeting_notes = f"""

## Meeting Notes - {today}

**Attendees:** Alice Smith, Bob Johnson, Charlie Davis

**Key Decisions:**
- Budget approved at $50,000 for Q1 2026
- Timeline adjusted: Launch moved to March 15, 2026
- New team member joining: Diana Martinez (Senior Developer)

**Action Items:**
- Alice: Finalize budget allocation by next week
- Bob: Update project timeline in tracking system
- Charlie: Coordinate Diana's onboarding schedule

**Next Meeting:** {today} (weekly standup)

---
"""

    print("=" * 60)
    print("Google Docs Meeting Notes Merger")
    print("=" * 60)
    print()

    # Initialize editor and inserter
    print("Initializing Google Docs editor...")
    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)

    try:
        # First, analyze the document to show what's there
        print(f"\nAnalyzing document...")
        analysis = editor.analyze_document(doc_url, include_comments=True)

        print(f"\n✓ Document loaded: {analysis.title}")
        print(f"  Sections: {len(analysis.sections)}")
        print(f"  Comments: {len(analysis.comments)}")

        if analysis.comments:
            print(f"\n  Existing comments:")
            for i, comment in enumerate(analysis.comments, 1):
                print(f"    {i}. {comment.author}: \"{comment.content[:50]}...\"")

        # Merge the meeting notes
        print(f"\nMerging meeting notes into document...")
        print(f"  Strategy: Safe insertion (preserve all comments)")
        print()

        result = inserter.merge_content(
            doc_url=doc_url,
            content=meeting_notes,
            section=None,  # Will insert at end
            options=MergeOptions(
                preserve_comments=True,
                comment_strategy='preserve',
                add_source_comment=True,
                source_description=f"team meeting on {today}"
            )
        )

        # Show result
        if result['success']:
            print("✅ SUCCESS!")
            print()
            print(f"  Message: {result['message']}")
            print(f"  Insertion point: Index {result['insertion_point'].index}")
            print(f"  Comments preserved: {result['comments_preserved']}")
            print()
            print("Meeting notes have been merged into the document!")
            print()
            print("You can view the updated document at:")
            print(f"  {doc_url}")
        else:
            print("❌ FAILED")
            print()
            print(f"  Error: {result.get('message', 'Unknown error')}")

            if result.get('requires_user_decision'):
                print()
                print("⚠️  User decision required:")
                print(f"  This insertion would affect {len(result['affected_comments'])} comment(s)")
                print()
                print("Options:")
                for option in result.get('options', []):
                    print(f"  - {option}")

    except ValueError as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
    except PermissionError as e:
        print(f"\n✗ Permission Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()
    print("=" * 60)


if __name__ == '__main__':
    main()
