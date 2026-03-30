#!/usr/bin/env python3
"""
Example: Read and display a Google Doc's content and structure.

Usage:
    python examples/read_document.py <doc_url_or_id>

Example:
    python examples/read_document.py https://docs.google.com/document/d/ABC123/edit
    python examples/read_document.py ABC123
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gdocs_editor import GoogleDocsEditor


def main():
    if len(sys.argv) < 2:
        print("Usage: python read_document.py <doc_url_or_id>")
        print("\nExample:")
        print("  python read_document.py https://docs.google.com/document/d/ABC123/edit")
        print("  python read_document.py ABC123")
        sys.exit(1)

    doc_url_or_id = sys.argv[1]

    # Initialize editor (will authenticate if needed)
    editor = GoogleDocsEditor()

    try:
        # Display document structure
        editor.print_document_structure(doc_url_or_id)

    except ValueError as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
    except PermissionError as e:
        print(f"\n✗ Permission Error: {e}")
        print("\nMake sure:")
        print("  1. The document URL is correct")
        print("  2. You have at least 'View' access to the document")
        print("  3. The document is not in the trash")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
