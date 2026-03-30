#!/usr/bin/env python3
"""
Execute ForSured Integration - Add new section to Product Plan.

Inserts the organized feedback and meeting notes as a new section
"2.9 Recent Feedback & Updates" before the "Document Status" section.
"""

import sys
from pathlib import Path

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from scripts.gdocs_editor import GoogleDocsEditor


def main():
    """Execute the integration by adding new section."""

    print("\n" + "="*80)
    print("EXECUTE FORSURED INTEGRATION")
    print("="*80 + "\n")

    # Read the prepared content
    content_file = Path(__file__).parent / "forsured_integration_content.txt"

    if not content_file.exists():
        print("❌ Error: Content file not found.")
        print("   Run integrate_forsured_smart.py first to generate the content.")
        return False

    content = content_file.read_text()

    print(f"✅ Loaded content: {len(content)} characters")
    print(f"   Content file: {content_file}\n")

    # Initialize editor
    editor = GoogleDocsEditor()

    # Get target document
    target_url = "https://docs.google.com/document/d/1NBkFTug7xEi8ZnkJ98mWFmOhE4sPgt2Pr9to_9KN8SE/edit?tab=t.0"
    doc_id = editor.extract_doc_id(target_url)

    print("📚 Reading target document...")
    target = editor.analyze_document(target_url, include_comments=False)
    print(f"✅ Target: {target.title}")
    print(f"   {target.total_chars} characters, {len(target.sections)} sections\n")

    # Find the "Document Status" section to insert before it
    document_status_section = None
    for section in target.sections:
        if 'document status' in section['heading'].lower():
            document_status_section = section
            break

    if not document_status_section:
        print("❌ Error: Could not find 'Document Status' section")
        return False

    insert_index = document_status_section['start_index']

    print(f"📍 Insertion point:")
    print(f"   Section: {document_status_section['heading']}")
    print(f"   Index: {insert_index}")
    print(f"   Will insert new section before 'Document Status'\n")

    # Prepare the API request
    print("🔧 Preparing API request...\n")

    # Add section heading as Heading 2 (same level as other major sections)
    requests = []

    # Insert the content
    requests.append({
        'insertText': {
            'location': {'index': insert_index},
            'text': content + '\n\n'
        }
    })

    # Format the "2.9 Recent Feedback & Updates" heading as Heading 2
    # After insertion, it will be at insert_index, and we need to format it
    heading_end = insert_index + len("2.9 Recent Feedback & Updates")

    requests.append({
        'updateParagraphStyle': {
            'range': {
                'startIndex': insert_index,
                'endIndex': heading_end
            },
            'paragraphStyle': {
                'namedStyleType': 'HEADING_2'
            },
            'fields': 'namedStyleType'
        }
    })

    # Preview the request
    print("📝 Request summary:")
    print(f"   • Insert {len(content)} characters at index {insert_index}")
    print(f"   • Format heading as HEADING_2")
    print(f"   • Total API requests: {len(requests)}\n")

    # Confirm before executing
    print("="*80)
    print("⚠️  READY TO EXECUTE")
    print("="*80 + "\n")
    print("This will add a new section '2.9 Recent Feedback & Updates' to:")
    print(f"  {target.title}")
    print(f"  {target_url}\n")
    print("The section will be inserted before 'Document Status' and will contain")
    print("all 26 organized semantic units from the two source documents.\n")

    # For safety, this script will execute
    # To make it interactive, uncomment the following:
    # response = input("Proceed with integration? (yes/no): ")
    # if response.lower() != 'yes':
    #     print("\n❌ Integration cancelled by user")
    #     return False

    # Execute the integration
    print("⚙️  Executing integration...\n")

    try:
        editor._ensure_authenticated()
        result = editor.docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()

        print("✅ Integration successful!")
        print(f"   Replies: {len(result.get('replies', []))}")
        print(f"\n   Document updated: {target_url}\n")

        print("="*80)
        print("NEXT STEPS")
        print("="*80 + "\n")
        print("1. Open the document and review the new section")
        print("2. Manually move items to their appropriate sections as needed")
        print("3. Update existing sections based on the feedback")
        print("4. Archive or delete the '2.9 Recent Feedback & Updates' section")
        print("   once all items have been addressed\n")

        return True

    except Exception as e:
        print(f"❌ Integration failed: {e}")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
