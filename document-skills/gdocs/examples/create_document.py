#!/usr/bin/env python3
"""
Example: Create a new Google Doc.

This script demonstrates how to create new Google Docs with optional initial content.
"""

import sys
from pathlib import Path

# Add parent directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gdocs_editor import GoogleDocsEditor


def main():
    print("="*60)
    print("Google Docs API - Create Document Example")
    print("="*60)
    print()

    # Initialize the editor
    editor = GoogleDocsEditor()

    # Example 1: Create a blank document
    print("Creating a blank document...")
    result = editor.create_document(
        title="My New Document"
    )

    print(f"\n✓ Created blank document:")
    print(f"  Title: {result['title']}")
    print(f"  ID: {result['doc_id']}")
    print(f"  URL: {result['doc_url']}")

    # Example 2: Create a document with initial content
    print("\n" + "="*60)
    print("Creating a document with initial content...")

    initial_content = """Welcome to My Document

This is the initial content added when the document was created.

You can add:
- Text
- Multiple paragraphs
- Any content you want

The document is ready to edit!"""

    result = editor.create_document(
        title="Document with Initial Content",
        initial_content=initial_content
    )

    print(f"\n✓ Created document with content:")
    print(f"  Title: {result['title']}")
    print(f"  ID: {result['doc_id']}")
    print(f"  URL: {result['doc_url']}")

    print("\n" + "="*60)
    print("✓ Done! Open the URLs above to view your new documents.")
    print("="*60)


if __name__ == '__main__':
    main()
