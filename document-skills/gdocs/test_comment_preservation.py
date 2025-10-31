#!/usr/bin/env python3
"""
Test comment preservation strategy.

This script tests whether comments survive when we:
1. Insert text within the commented range
2. Delete surrounding text

Original text: "Todo application addressing"
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                (comment attached)

Goal: Replace with "making the comment"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scripts.gdocs_editor import GoogleDocsEditor
from googleapiclient.discovery import build


def main():
    doc_id = "1rW2_vw5GzsTIbj_5fxXLnFnJ1-htCYt__AHI0u4FZTI"

    print("="*60)
    print("Comment Preservation Test")
    print("="*60)

    editor = GoogleDocsEditor()
    editor._ensure_authenticated()

    # Step 1: Get current document state
    print("\nStep 1: Reading current document and comments...")
    doc = editor.get_document(doc_id)
    analysis = editor.analyze_document(doc_id)

    # Find the comment
    target_comment = None
    for comment in analysis.comments:
        if "Todo application addressing" in comment.anchor:
            target_comment = comment
            break

    if not target_comment:
        print("ERROR: Could not find comment on 'Todo application addressing'")
        print(f"Found {len(analysis.comments)} comments:")
        for c in analysis.comments:
            print(f"  - On text: {c.anchor}")
        return

    print(f"\n✓ Found comment:")
    print(f"  Author: {target_comment.author}")
    print(f"  Content: {target_comment.content}")
    print(f"  Anchor: {target_comment.anchor}")

    # Step 2: Find the text in the document
    print("\nStep 2: Locating text in document...")

    # Search for the sentence containing our target text
    content = analysis.content
    target_sentence = '"AchieveIt" will be a user-friendly and feature-rich Todo application addressing the shortcomings of current market offerings.'

    if target_sentence not in content:
        print(f"ERROR: Could not find target sentence in document")
        print(f"Looking for: {target_sentence}")
        return

    print(f"✓ Found target sentence")

    # Find the exact location in the document structure
    body = doc.get('body', {})
    content_elements = body.get('content', [])

    target_start_index = None
    target_end_index = None
    original_text = "Todo application addressing"

    for element in content_elements:
        if 'paragraph' in element:
            para = element['paragraph']
            para_text = editor._extract_paragraph_text(para)

            if original_text in para_text:
                # Found the paragraph! Now find the exact text run
                for elem in para.get('elements', []):
                    if 'textRun' in elem:
                        text = elem['textRun'].get('content', '')
                        if original_text in text:
                            # Calculate exact indices
                            start_index = elem.get('startIndex', 0)
                            text_offset = text.index(original_text)
                            target_start_index = start_index + text_offset
                            target_end_index = target_start_index + len(original_text)
                            break
                break

    if target_start_index is None:
        print(f"ERROR: Could not locate exact position of '{original_text}'")
        return

    print(f"✓ Located text at indices {target_start_index}-{target_end_index}")

    # Step 3: Execute the replacement strategy
    print("\nStep 3: Executing comment-preserving replacement...")
    print(f"  Original: '{original_text}'")
    print(f"  Target: 'making the comment'")

    # Build the requests
    requests = []

    # Request 1: Insert "making the comment " at position right after "Todo application "
    # This inserts into the middle of the commented range
    insert_position = target_start_index + len("Todo application ")
    insert_text = "making the comment "

    print(f"\n  Sub-step 1: Insert '{insert_text}' at index {insert_position}")
    requests.append({
        'insertText': {
            'location': {'index': insert_position},
            'text': insert_text
        }
    })

    # Request 2: Delete "addressing" (after our insertion, so adjust index)
    # After insertion, "addressing" is now further ahead
    delete_start = insert_position + len(insert_text)
    delete_end = target_end_index + len(insert_text)

    print(f"  Sub-step 2: Delete 'addressing' from {delete_start} to {delete_end}")
    requests.append({
        'deleteContentRange': {
            'range': {
                'startIndex': delete_start,
                'endIndex': delete_end
            }
        }
    })

    # Request 3: Delete "Todo application " at the beginning
    # Indices stay the same since we're deleting from earlier position
    print(f"  Sub-step 3: Delete 'Todo application ' from {target_start_index} to {insert_position}")
    requests.append({
        'deleteContentRange': {
            'range': {
                'startIndex': target_start_index,
                'endIndex': insert_position
            }
        }
    })

    # Execute all requests in a single batchUpdate
    print("\nExecuting batch update...")
    try:
        result = editor.docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()

        print("✓ Batch update completed successfully!")

    except Exception as e:
        print(f"ERROR: Batch update failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 4: Verify the result
    print("\nStep 4: Verifying result...")
    print("Waiting 2 seconds for changes to propagate...")
    import time
    time.sleep(2)

    # Re-read the document
    analysis_after = editor.analyze_document(doc_id)

    print(f"\n✓ Document updated")
    print(f"  Comments before: {len(analysis.comments)}")
    print(f"  Comments after: {len(analysis_after.comments)}")

    # Check if our comment survived
    comment_survived = False
    new_anchor = None

    for comment in analysis_after.comments:
        if comment.comment_id == target_comment.comment_id:
            comment_survived = True
            new_anchor = comment.anchor
            print(f"\n✅ COMMENT SURVIVED!")
            print(f"  Comment ID: {comment.comment_id}")
            print(f"  Author: {comment.author}")
            print(f"  Content: {comment.content}")
            print(f"  New anchor: '{new_anchor}'")
            break

    if not comment_survived:
        print(f"\n❌ COMMENT LOST")
        print(f"  The comment did not survive the update")
        print(f"  This means the strategy didn't work as expected")

    # Verify the text changed
    content_after = analysis_after.content
    if "making the comment" in content_after:
        print(f"\n✓ Text successfully replaced")
        print(f"  New text appears in document")
    else:
        print(f"\n⚠️  Warning: Could not find new text in document")

    print("\n" + "="*60)
    print("Test complete!")
    print("="*60)


if __name__ == '__main__':
    main()
