#!/usr/bin/env python3
"""
Integrate ForSured project updates into product plan document.

Merges Brokerflow review and GC/Sub flow meeting notes into the
ForSured Product Plan document using intelligent content integration.
"""

import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.content_integrator import ContentIntegrator


def main():
    """Run ForSured document integration."""

    print("\n" + "="*80)
    print("FORSURED PROJECT UPDATE INTEGRATION")
    print("="*80 + "\n")

    # Document URLs
    doc1_url = "https://docs.google.com/document/d/1h0ydRba1RQ9qfqbTOXaVeFzpySChuKppyp48IhTX-S4/edit?tab=t.0"
    doc2_url = "https://docs.google.com/document/d/1pNrE66Ojlj-MxC1dm5any_qIwwYCZjMf_4DEbbRwgI0/edit?tab=t.xa7iwfsfsntw"
    target_url = "https://docs.google.com/document/d/1NBkFTug7xEi8ZnkJ98mWFmOhE4sPgt2Pr9to_9KN8SE/edit?tab=t.0"

    # Initialize editor
    editor = GoogleDocsEditor()

    # Step 1: Read all documents
    print("📚 Reading documents...")
    print("-" * 80 + "\n")

    doc1 = editor.analyze_document(doc1_url, include_comments=False)
    print(f"✅ Source 1: {doc1.title}")
    print(f"   {doc1.total_chars} characters, {len(doc1.sections)} sections\n")

    doc2 = editor.analyze_document(doc2_url, include_comments=False)
    print(f"✅ Source 2: {doc2.title}")
    print(f"   {doc2.total_chars} characters, {len(doc2.sections)} sections\n")

    target = editor.analyze_document(target_url, include_comments=False)
    print(f"✅ Target: {target.title}")
    print(f"   {target.total_chars} characters, {len(target.sections)} sections\n")

    # Step 2: Combine source content
    print("\n" + "="*80)
    print("COMBINING SOURCE CONTENT")
    print("="*80 + "\n")

    combined_content = f"""
Brokerflow Review Feedback
===========================

{doc1.content}


GC/Subcontractor Flow Meeting Notes
====================================

{doc2.content}
"""

    print(f"Combined content: {len(combined_content.split())} words\n")

    # Step 3: Prepare target sections for integration
    print("\n" + "="*80)
    print("PREPARING TARGET DOCUMENT")
    print("="*80 + "\n")

    # Convert sections to format expected by integrator
    document_sections = []
    for section in target.sections:
        document_sections.append({
            'heading': section['heading'],
            'level': section['level'],
            'start_index': section['start_index'],
            'end_index': section['end_index'],
            'content': ''  # We'll extract this if needed
        })

    print(f"Target has {len(document_sections)} sections:\n")
    for i, section in enumerate(document_sections[:10], 1):
        indent = '  ' * (int(section['level']) - 1) if section['level'].isdigit() else ''
        print(f"  {i}. {indent}{section['heading']}")

    if len(document_sections) > 10:
        print(f"  ... and {len(document_sections) - 10} more sections\n")

    # Step 4: Create integrator and get plan
    print("\n" + "="*80)
    print("ANALYZING INTEGRATION PLAN")
    print("="*80 + "\n")

    integrator = ContentIntegrator(
        document_service=None,  # Will be set when ready to execute
        show_preview=True,
        dry_run=True  # Start in preview mode
    )

    # Auto-detect content type and get plan
    plan = integrator.get_integration_plan(
        combined_content,
        document_sections
    )

    print(f"Content Type: {plan['content_type']}")
    print(f"Semantic Units Extracted: {plan['units_extracted']}")
    print(f"Units Matched to Sections: {plan['units_matched']}")
    print(f"Estimated Changes: {plan['estimated_changes']}")
    print(f"Average Confidence: {plan['strategies']['avg_confidence']:.0%}\n")

    print("Strategy Breakdown:")
    print(f"  • ADD: {plan['strategies']['actions']['add']} new items")
    print(f"  • UPDATE: {plan['strategies']['actions']['update']} replacements")
    print(f"  • MERGE: {plan['strategies']['actions']['merge']} combinations")
    print(f"  • SKIP: {plan['strategies']['actions']['skip']} duplicates")
    print()

    # Step 5: Show detailed preview
    print("\n" + "="*80)
    print("INTEGRATION PREVIEW (DRY RUN)")
    print("="*80 + "\n")

    print("Running integration in preview mode...\n")

    result = integrator.integrate_content(
        combined_content,
        document_sections,
        content_type=plan['content_type']
    )

    # Step 6: Summary
    print("\n" + "="*80)
    print("INTEGRATION SUMMARY")
    print("="*80 + "\n")

    if result.success:
        print(f"✅ Preview Complete")
        print(f"   • {result.actions_executed} changes would be applied")
        print(f"   • {len(result.sections_modified)} sections would be modified")
        print(f"   • Processing time: {result.execution_time:.3f}s")

        if result.sections_modified:
            print(f"\nSections to be modified:")
            for section in result.sections_modified:
                print(f"   • {section}")
    else:
        print(f"❌ Preview Failed")
        for error in result.errors:
            print(f"   • {error}")

    # Step 7: Execution instructions
    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80 + "\n")

    print("This was a DRY RUN preview. No changes were made to the document.")
    print()
    print("To execute the integration:")
    print("  1. Review the preview above carefully")
    print("  2. Set dry_run=False in the script")
    print("  3. Set document_service=editor.docs_service")
    print("  4. Re-run the script to apply changes")
    print()
    print("="*80 + "\n")

    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
