#!/usr/bin/env python3
"""
Intelligent merge of meeting notes into Google Doc.

Uses Claude to analyze document structure and determine
optimal merge strategy instead of just appending.

Usage:
    export ANTHROPIC_API_KEY=your_key
    python intelligent_merge.py notes.txt
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.intelligent_merger import IntelligentMerger
from datetime import datetime


def main():
    print("=" * 60)
    print("🤖 Intelligent Google Docs Merger")
    print("=" * 60)
    print()

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ERROR: ANTHROPIC_API_KEY environment variable not set")
        print()
        print("Please set your API key:")
        print("  export ANTHROPIC_API_KEY='your_key_here'")
        print()
        sys.exit(1)

    # Your Todo App document
    doc_url = "https://docs.google.com/document/d/1rW2_vw5GzsTIbj_5fxXLnFnJ1-htCYt__AHI0u4FZTI/edit"

    # Get meeting notes
    meeting_notes = None

    if len(sys.argv) > 1:
        arg = sys.argv[1]

        # Check if it's a file
        if Path(arg).exists():
            print(f"📄 Reading notes from file: {arg}")
            meeting_notes = Path(arg).read_text()
        else:
            # Treat as direct text
            print("📄 Using provided text as meeting notes")
            meeting_notes = arg
    else:
        # Interactive mode
        print("📄 Paste your meeting notes below.")
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
    print("🔧 Initializing...")
    editor = GoogleDocsEditor()
    editor._ensure_authenticated()
    merger = IntelligentMerger(editor)

    print("✓ Ready")
    print()

    # Confirm before merging
    response = input("🤔 Analyze and intelligently merge these notes? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        sys.exit(0)

    print()
    print("=" * 60)

    # Intelligent merge
    today = datetime.now().strftime('%Y-%m-%d %H:%M')

    try:
        result = merger.analyze_and_merge(
            doc_url=doc_url,
            meeting_notes=meeting_notes,
            add_source_comment=True,
            source_description=f"customer feedback meeting on {today}"
        )

        # Show results
        print()
        print("=" * 60)

        if result['success']:
            print("✅ SUCCESS!")
            print()
            print(f"  Strategy Used: {result.get('strategy_used', 'N/A')}")
            print(f"  Reason: {result.get('strategy_reason', 'N/A')}")
            print()
            print(f"  ✓ Comments preserved: {result['comments_preserved']}")

            if result.get('new_comment_id'):
                print(f"  ✓ Source comment created: {result['new_comment_id']}")

            print()
            print("View the updated document at:")
            print(f"  {doc_url}")
            print()
            print("✨ Your meeting notes have been intelligently merged!")
        else:
            print("❌ FAILED")
            print()
            print(f"  Error: {result.get('message', 'Unknown error')}")

            if 'error' in result:
                print(f"  Details: {result['error']}")

    except Exception as e:
        print()
        print("=" * 60)
        print("❌ ERROR")
        print()
        print(f"  {str(e)}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)


if __name__ == '__main__':
    main()
