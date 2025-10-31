#!/usr/bin/env python3
"""
Test the Google Docs skill with real meeting notes.

Usage:
    python test_with_real_notes.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.content_inserter import ContentInserter, MergeOptions
from datetime import datetime


def main():
    print("=" * 60)
    print("Google Docs Skill - Real Meeting Notes Test")
    print("=" * 60)
    print()

    # Your Todo App document
    doc_url = "https://docs.google.com/document/d/1rW2_vw5GzsTIbj_5fxXLnFnJ1-htCYt__AHI0u4FZTI/edit"

    # Get meeting notes from user
    print("Paste your meeting notes below.")
    print("When done, press Ctrl+D (Mac/Linux) or Ctrl+Z then Enter (Windows):")
    print()

    meeting_notes = sys.stdin.read()

    if not meeting_notes.strip():
        print("No meeting notes provided. Exiting.")
        sys.exit(1)

    print()
    print("-" * 60)
    print("Meeting notes received:")
    print("-" * 60)
    print(meeting_notes[:200] + "..." if len(meeting_notes) > 200 else meeting_notes)
    print("-" * 60)
    print()

    # Initialize
    print("Initializing Google Docs editor...")
    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)

    # Show current document state
    print("Analyzing current document state...")
    analysis = editor.analyze_document(doc_url, include_comments=True)
    print(f"  Document: {analysis.title}")
    print(f"  Current length: {analysis.total_chars} characters")
    print(f"  Existing comments: {len(analysis.comments)}")
    print()

    # Confirm before merging
    response = input("Merge these notes into the document? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        sys.exit(0)

    # Merge the notes
    print()
    print("Merging meeting notes into document...")
    today = datetime.now().strftime('%Y-%m-%d')

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
        print(f"  Insertion point: Index {result['insertion_point'].index}")
        print(f"  Strategy: {result['insertion_point'].reason}")
        print(f"  Comments preserved: {result['comments_preserved']}")

        if result['new_comment_id']:
            print(f"  Source comment ID: {result['new_comment_id']}")
            print(f"  Comment content: \"📝 Added from meeting notes on {today}\"")

        print()
        print(f"View the updated document at:")
        print(f"  {doc_url}")
    else:
        print("❌ FAILED")
        print()
        print(f"  Error: {result.get('message', 'Unknown error')}")

    print()
    print("=" * 60)


if __name__ == '__main__':
    main()
