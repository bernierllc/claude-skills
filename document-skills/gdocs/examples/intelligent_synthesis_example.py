#!/usr/bin/env python3
"""
Example: Intelligent Meeting Notes Synthesis

This example demonstrates the complete workflow for merging meeting notes
into a Google Doc with intelligent synthesis.

In production, Claude (in conversation) performs the analysis and synthesis.
This script shows the mechanics of the merge operation after synthesis.

Use case: You have detailed meeting notes (3000+ chars) and want to add
key insights to an executive proposal without dumping raw content.
"""

import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.content_inserter import ContentInserter, MergeOptions


def main():
    """
    Example workflow for intelligent meeting notes synthesis.

    Real-world flow:
    1. User provides meeting notes + Google Doc URL to Claude
    2. Claude analyzes document (purpose, tone, style, audience)
    3. Claude analyzes notes (extracts 3-5 key insights)
    4. Claude synthesizes content matching document style
    5. Claude shows preview and asks for approval
    6. This script executes the merge after approval
    """

    # Initialize editor
    print("Initializing Google Docs Editor...")
    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)

    # Example: Document URL
    doc_url = input("\nEnter Google Doc URL: ")

    print("\n" + "="*70)
    print("STEP 1: Analyzing Document")
    print("="*70)

    # Read and analyze the target document
    analysis = editor.analyze_document(doc_url, include_comments=True)

    print(f"\n📄 Document: {analysis.title}")
    print(f"Total characters: {analysis.total_chars:,}")
    print(f"Sections found: {len(analysis.sections)}")
    print(f"Existing comments: {len(analysis.comments)}")

    print("\n📋 Document Structure:")
    for section in analysis.sections[:5]:  # Show first 5 sections
        print(f"  - {section['heading']} ({section['level']})")

    # Example: Raw meeting notes (in real use, Claude analyzes these)
    print("\n" + "="*70)
    print("STEP 2: Source Material Analysis")
    print("="*70)

    print("\n📝 Original Meeting Notes (example):")
    original_notes = """
📝 Meeting Notes — Customer Feedback on To-Do App
Date: October 31, 2025
Attendees: Product Manager: Sarah Lin, Customer: Alex Rivera

1. Purpose: To gather customer insights on productivity app features...
2. Customer's Current To-Do App Usage:
   - App: Todoist (primary), used daily for work and personal planning
   - Keeps multiple project lists across devices
   - Integrates with Google Calendar and Slack

3. Pain Points & Improvement Areas:
   - Overwhelming task lists: Wants more intelligent grouping
   - Limited Collaboration: Hard to assign and track shared tasks
   - Lack of Context: Tasks often need attachments

4. Desired Features: [6 feature requests with details]
5. Next Steps: [3 action items]
"""
    print(original_notes)
    print(f"Character count: {len(original_notes):,}")

    # Example: Synthesized content (in real use, Claude does this)
    print("\n" + "="*70)
    print("STEP 3: Intelligent Synthesis")
    print("="*70)

    print("\n💡 Claude's Analysis:")
    print("  Document: Executive proposal, formal tone, concise sections")
    print("  Audience: Managers/executives")
    print("  Section pattern: 2-3 sentences per key point")
    print("\n  Key insights extracted:")
    print("    1. Pain point: 'Overwhelming task lists'")
    print("    2. Pain point: 'Lack of context'")
    print("    3. Feature gap: AI-assisted prioritization")
    print("    4. Feature gap: Location-aware reminders")

    synthesized_content = """
Recent customer research with active Todoist users validates this approach and reveals specific market opportunities. Users consistently report "overwhelming task lists" and "lack of context" as primary frustrations, directly supporting our planned focus mode and contextual attachment features. Additionally, strong demand emerged for AI-assisted prioritization and location-aware reminders, capabilities absent in current market leaders.
"""

    print("\n✨ Synthesized Content (440 chars vs 3,000+ original):")
    print("-" * 70)
    print(synthesized_content.strip())
    print("-" * 70)

    # Ask which section to target
    print("\n" + "="*70)
    print("STEP 4: Insertion Point Selection")
    print("="*70)

    print("\nAvailable sections:")
    for i, section in enumerate(analysis.sections, 1):
        print(f"  {i}. {section['heading']}")

    section_name = input("\nEnter section name (or press Enter for 'Market Analysis'): ").strip()
    if not section_name:
        section_name = "Market Analysis"

    # Show preview
    print("\n" + "="*70)
    print("STEP 5: Preview Before Insertion")
    print("="*70)

    print(f"\n📍 Insertion location: End of '{section_name}' section")
    print(f"📝 Content to add: {len(synthesized_content.strip())} characters")
    print(f"💬 Attribution comment: 'Enhanced with insights from customer feedback (10/31/25)'")
    print("\n✅ Formatting: NORMAL_TEXT style (prevents header inheritance)")
    print("✅ Comment preservation: Existing comments will be preserved")

    # Confirm
    proceed = input("\n🚀 Execute merge? (yes/no): ").strip().lower()
    if proceed not in ['yes', 'y']:
        print("\n❌ Merge cancelled")
        return

    # Execute the merge
    print("\n" + "="*70)
    print("STEP 6: Executing Merge")
    print("="*70)

    result = inserter.merge_content(
        doc_url=doc_url,
        content=synthesized_content,
        section=section_name,
        options=MergeOptions(
            preserve_comments=True,
            add_source_comment=True,
            source_description="customer feedback (10/31/25)"
        )
    )

    # Show results
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)

    if result['success']:
        print("\n✅ Success!")
        print(f"\n📍 Insertion index: {result['insertion_point'].index}")
        print(f"📊 Reason: {result['insertion_point'].reason}")
        print(f"💬 Comment created: ID {result.get('new_comment_id', 'N/A')}")
        print(f"🔒 Comments preserved: {result['comments_preserved']}")
        print(f"\n📄 View document: {doc_url}")

        print("\n" + "="*70)
        print("VERIFICATION CHECKLIST")
        print("="*70)
        print("\nCheck the document for:")
        print("  [ ] Content appears in correct section")
        print("  [ ] Formatting matches document style (not header)")
        print("  [ ] Length is appropriate (not 10x longer)")
        print("  [ ] Tone matches existing content")
        print("  [ ] Attribution comment exists")
        print("  [ ] Existing comments preserved")
    else:
        print(f"\n❌ Failed: {result.get('message', 'Unknown error')}")
        if 'error' in result:
            print(f"\n🔍 Error details: {result['error']}")


if __name__ == '__main__':
    print("""
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║        Google Docs Intelligent Synthesis Example                     ║
║                                                                       ║
║  This example demonstrates the complete workflow for merging          ║
║  meeting notes into Google Docs with intelligent synthesis.          ║
║                                                                       ║
║  Key Transformation:                                                  ║
║    Input:  3,000+ character meeting transcript                       ║
║    Output: 440 character executive summary                           ║
║    Result: Presentation-ready, matches document tone                 ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
    """)

    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
