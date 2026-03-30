#!/usr/bin/env python3
"""
Quick Start: Simple Content Merge

This is the simplest possible example of merging content into a Google Doc.
Use this for testing and understanding the basic mechanics.

For intelligent synthesis, see: intelligent_synthesis_example.py
"""

import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.content_inserter import ContentInserter, MergeOptions


def main():
    # Initialize
    print("Initializing Google Docs Editor...")
    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)

    # Get document URL
    doc_url = input("Enter Google Doc URL: ")

    # Content to insert (in real use, this would be Claude's synthesis)
    content = input("\nEnter content to insert: ")

    # Optional: Target section
    section = input("Target section name (or press Enter to append): ").strip() or None

    # Execute merge
    print("\n🚀 Merging content...")
    result = inserter.merge_content(
        doc_url=doc_url,
        content=f"\n\n{content}\n\n",
        section=section,
        options=MergeOptions(
            preserve_comments=True,
            add_source_comment=True,
            source_description=f"quick merge on {os.popen('date +%Y-%m-%d').read().strip()}"
        )
    )

    # Show results
    if result['success']:
        print("\n✅ Success!")
        print(f"Inserted at index: {result['insertion_point'].index}")
        print(f"Comment ID: {result.get('new_comment_id', 'N/A')}")
        print(f"\nView: {doc_url}")
    else:
        print(f"\n❌ Failed: {result.get('message', 'Unknown error')}")


if __name__ == '__main__':
    print("\n=== Google Docs Quick Merge Example ===\n")
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled")
    except Exception as e:
        print(f"\n\nError: {e}")
