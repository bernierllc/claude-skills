#!/usr/bin/env python3
"""
Merge meeting notes into your Todo App Google Doc.

Usage:
    # With notes file:
    python merge_notes.py notes.txt

    # With direct text:
    python merge_notes.py "## Meeting Notes\n\nContent here..."

    # Interactive (paste notes):
    python merge_notes.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.content_inserter import ContentInserter, MergeOptions
from datetime import datetime


def main():
    print("=" * 60)
    print("Google Docs Skill - Merge Meeting Notes")
    print("=" * 60)
    print()

    # Your Todo App document
    doc_url = "https://docs.google.com/document/d/1rW2_vw5GzsTIbj_5fxXLnFnJ1-htCYt__AHI0u4FZTI/edit"

    # Get meeting notes
    meeting_notes = None

    if len(sys.argv) > 1:
        arg = sys.argv[1]

        # Check if it's a file
        if Path(arg).exists():
            print(f"Reading notes from file: {arg}")
            meeting_notes = Path(arg).read_text()
        else:
            # Treat as direct text
            print("Using provided text as meeting notes")
            meeting_notes = arg
    else:
        # Interactive mode
        print("Paste your meeting notes below.")
        print("When done, press Ctrl+D (Mac/Linux) or Ctrl+Z then Enter (Windows):")
        print()
        meeting_notes = sys.stdin.read()

    if not meeting_notes or not meeting_notes.strip():
        print("❌ No meeting notes provided. Exiting.")
        sys.exit(1)

    print()
    print("-" * 60)
    print("Meeting notes preview:")
    print("-" * 60)
    preview = meeting_notes[:300]
    if len(meeting_notes) > 300:
        preview += "\n... (" + str(len(meeting_notes) - 300) + " more characters)"
    print(preview)
    print("-" * 60)
    print()

    # Initialize
    print("Initializing Google Docs editor...")
    editor = GoogleDocsEditor()
    editor._ensure_authenticated()
    inserter = ContentInserter(editor)

    # Show current document state
    print("Analyzing current document state...")
    analysis = editor.analyze_document(doc_url, include_comments=True)
    print(f"  ✓ Document: {analysis.title}")
    print(f"  ✓ Current length: {analysis.total_chars} characters")
    print(f"  ✓ Existing comments: {len(analysis.comments)}")

    if analysis.comments:
        print()
        print("  Recent comments:")
        for i, comment in enumerate(analysis.comments[-3:], 1):
            print(f"    {i}. [{comment.author}] \"{comment.content[:40]}...\"")

    print()

    # Confirm before merging
    response = input("Merge these notes into the document? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        sys.exit(0)

    # Merge the notes
    print()
    print("Merging meeting notes...")
    today = datetime.now().strftime('%Y-%m-%d %H:%M')

    result = inserter.merge_content(
        doc_url=doc_url,
        content=meeting_notes,
        options=MergeOptions(
            preserve_comments=True,
            add_source_comment=True,
            source_description=f"meeting notes on {today}"
        )
    )

    # Show results
    print()
    if result['success']:
        print("✅ SUCCESS!")
        print()
        print(f"  ✓ Notes merged at index {result['insertion_point'].index}")
        print(f"  ✓ Strategy: {result['insertion_point'].reason}")
        print(f"  ✓ Comments preserved: {result['comments_preserved']}")

        if result['new_comment_id']:
            print(f"  ✓ Source comment created: {result['new_comment_id']}")

        print()
        print("View the updated document at:")
        print(f"  {doc_url}")
        print()
        print("✨ Your meeting notes have been successfully merged!")
    else:
        print("❌ FAILED")
        print()
        print(f"  Error: {result.get('message', 'Unknown error')}")

        if 'error' in result:
            print(f"  Details: {result['error']}")

    print()
    print("=" * 60)


if __name__ == '__main__':
    main()
