#!/usr/bin/env python3
"""
Example: Read and display comments from a Google Doc.

Usage:
    python examples/read_comments.py <doc_url_or_id>

Example:
    python examples/read_comments.py https://docs.google.com/document/d/ABC123/edit
    python examples/read_comments.py ABC123
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gdocs_editor import GoogleDocsEditor


def main():
    if len(sys.argv) < 2:
        print("Usage: python read_comments.py <doc_url_or_id>")
        print("\nExample:")
        print("  python read_comments.py https://docs.google.com/document/d/ABC123/edit")
        print("  python read_comments.py ABC123")
        sys.exit(1)

    doc_url_or_id = sys.argv[1]

    # Initialize editor (will authenticate if needed)
    editor = GoogleDocsEditor()

    try:
        print("Analyzing document and retrieving comments...\n")

        # Analyze document with comments
        analysis = editor.analyze_document(doc_url_or_id, include_comments=True)

        # Display basic info
        print(f"{'='*60}")
        print(f"Document: {analysis.title}")
        print(f"ID: {analysis.doc_id}")
        print(f"{'='*60}\n")

        # Display comments
        if analysis.comments:
            print(f"Found {len(analysis.comments)} comment(s):\n")

            for i, comment in enumerate(analysis.comments, 1):
                print(f"{i}. Comment by {comment.author}")
                print(f"   ID: {comment.comment_id}")
                print(f"   Created: {comment.created_time.strftime('%Y-%m-%d %H:%M')}")
                print(f"   Resolved: {'Yes' if comment.resolved else 'No'}")

                if comment.anchor:
                    print(f"   On text: \"{comment.anchor[:60]}{'...' if len(comment.anchor) > 60 else ''}\"")

                print(f"   Content: {comment.content}")

                if comment.replies:
                    print(f"\n   Replies ({len(comment.replies)}):")
                    for reply in comment.replies:
                        print(f"      → {reply.author} ({reply.created_time.strftime('%Y-%m-%d %H:%M')})")
                        print(f"        {reply.content}")

                print()
        else:
            print("No comments found in this document.")

        print(f"{'='*60}")

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


if __name__ == '__main__':
    main()
