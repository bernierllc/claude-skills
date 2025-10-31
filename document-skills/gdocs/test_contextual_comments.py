#!/usr/bin/env python3
"""
Test script for contextual comments with paragraph location.

This tests the new create_comment_with_context() method that:
1. Searches for inserted text in the document
2. Creates a comment with rich context (paragraph number + excerpt)
3. Falls back to document-level if search fails

Note: Per Google's documentation, comments created via API are treated as
"unanchored" in Google Docs UI, but the comment body contains location info.
"""

import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.content_inserter import ContentInserter, MergeOptions


def main():
    print("="*70)
    print("Test: Contextual Comments with Paragraph Location")
    print("="*70)

    # Get document URL
    doc_url = input("\nEnter Google Doc URL: ").strip()
    if not doc_url:
        print("No URL provided")
        return

    print("\n" + "="*70)
    print("Step 1: Initialize Editor")
    print("="*70)

    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)

    print("✓ Editor initialized")

    print("\n" + "="*70)
    print("Step 2: Analyze Document")
    print("="*70)

    doc_id = editor.extract_doc_id(doc_url)
    analysis = editor.analyze_document(doc_id)

    print(f"✓ Document: {analysis.title}")
    print(f"✓ Sections: {len(analysis.sections)}")
    print(f"✓ Comments: {len(analysis.comments)}")

    print("\n" + "="*70)
    print("Step 3: Insert Test Content")
    print("="*70)

    # Test content with unique marker for easy searching
    test_content = """
This is a test insertion for contextual comments. The comment should include the paragraph number and an excerpt showing this exact text.
"""

    print(f"Content to insert: {test_content.strip()}")

    # Get target section
    section_name = input("\nTarget section (or press Enter for end of document): ").strip() or None

    result = inserter.merge_content(
        doc_url=doc_url,
        content=test_content,
        section=section_name,
        options=MergeOptions(
            preserve_comments=True,
            add_source_comment=True,
            source_description="contextual comment test (10/31/25)"
        )
    )

    print("\n" + "="*70)
    print("Step 4: Verify Results")
    print("="*70)

    if result['success']:
        print("✓ Content inserted successfully")
        print(f"✓ Insertion index: {result['insertion_point'].index}")

        if result.get('new_comment_id'):
            print(f"✓ Comment created: {result['new_comment_id']}")

            # Read the comment back to verify context
            print("\n" + "="*70)
            print("Step 5: Verify Comment Context")
            print("="*70)

            comments = editor.comment_manager.get_comments(doc_id, include_resolved=False)
            new_comment = next(
                (c for c in comments if c.comment_id == result['new_comment_id']),
                None
            )

            if new_comment:
                print("✓ Comment found in document")
                print(f"\nComment content:\n{new_comment.content}")

                # Check if it contains paragraph info
                if "Paragraph #" in new_comment.content:
                    print("\n✓ Comment contains paragraph location")
                else:
                    print("\n⚠️  Comment does not contain paragraph location (fallback mode)")

                if "Context:" in new_comment.content:
                    print("✓ Comment contains excerpt")
                else:
                    print("⚠️  Comment does not contain excerpt (fallback mode)")
            else:
                print("⚠️  Could not find comment in document")
        else:
            print("⚠️  No comment was created")

        print(f"\n📄 View document: {doc_url}")
    else:
        print(f"❌ Failed: {result.get('message', 'Unknown error')}")

    print("\n" + "="*70)
    print("What to Check in Google Docs UI:")
    print("="*70)
    print("1. Open the document in Google Docs")
    print("2. Click the comments icon (💬) to open comments panel")
    print("3. Find the newest comment")
    print("4. Verify it contains:")
    print("   - Source attribution ('Added from contextual comment test')")
    print("   - Paragraph number ('Paragraph #X')")
    print("   - Excerpt showing the inserted text")
    print("\n5. Note: Per Google's docs, the comment will be 'unanchored'")
    print("   (not highlighting specific text), but it will contain location info")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
