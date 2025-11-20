#!/usr/bin/env python3
"""
Example: Read and display a Google Slides presentation's content and structure.

Usage:
    python examples/read_presentation.py <presentation_url_or_id>

Example:
    python examples/read_presentation.py https://docs.google.com/presentation/d/ABC123/edit
    python examples/read_presentation.py ABC123
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gslides_editor import GoogleSlidesEditor


def main():
    if len(sys.argv) < 2:
        print("Usage: python read_presentation.py <presentation_url_or_id>")
        print("\nExample:")
        print("  python read_presentation.py https://docs.google.com/presentation/d/ABC123/edit")
        print("  python read_presentation.py ABC123")
        sys.exit(1)

    pres_url_or_id = sys.argv[1]

    # Initialize editor (will authenticate if needed)
    editor = GoogleSlidesEditor()

    try:
        # Display presentation structure
        editor.print_presentation_structure(pres_url_or_id)

    except ValueError as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
    except PermissionError as e:
        print(f"\n✗ Permission Error: {e}")
        print("\nMake sure:")
        print("  1. The presentation URL is correct")
        print("  2. You have at least 'View' access to the presentation")
        print("  3. The presentation is not in the trash")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
