#!/usr/bin/env python3
"""
Smart ForSured Integration - Creates dedicated section for feedback.

Instead of forcing feedback into existing sections, this creates a new
"Recent Feedback & Updates" section to consolidate all the new information,
allowing manual distribution later.
"""

import sys
from pathlib import Path

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.content_decomposer import ContentDecomposer


def main():
    """Smart integration with dedicated feedback section."""

    print("\n" + "="*80)
    print("FORSURED SMART INTEGRATION")
    print("="*80 + "\n")

    # Document URLs
    doc1_url = "https://docs.google.com/document/d/1h0ydRba1RQ9qfqbTOXaVeFzpySChuKppyp48IhTX-S4/edit?tab=t.0"
    doc2_url = "https://docs.google.com/document/d/1pNrE66Ojlj-MxC1dm5any_qIwwYCZjMf_4DEbbRwgI0/edit?tab=t.xa7iwfsfsntw"
    target_url = "https://docs.google.com/document/d/1NBkFTug7xEi8ZnkJ98mWFmOhE4sPgt2Pr9to_9KN8SE/edit?tab=t.0"

    editor = GoogleDocsEditor()

    # Read source documents
    print("📚 Reading source documents...")
    doc1 = editor.analyze_document(doc1_url, include_comments=False)
    doc2 = editor.analyze_document(doc2_url, include_comments=False)
    target = editor.analyze_document(target_url, include_comments=False)

    print(f"✅ Source 1: {doc1.title} ({doc1.total_chars} chars)")
    print(f"✅ Source 2: {doc2.title} ({doc2.total_chars} chars)")
    print(f"✅ Target: {target.title} ({target.total_chars} chars, {len(target.sections)} sections)\n")

    # Analyze content types
    print("\n" + "="*80)
    print("ANALYZING CONTENT")
    print("="*80 + "\n")

    decomposer = ContentDecomposer()

    # Analyze doc1 (Brokerflow review)
    units1 = decomposer.decompose(doc1.content, 'meeting_notes')
    types1 = {}
    for unit in units1:
        types1[unit.type] = types1.get(unit.type, 0) + 1

    print(f"Source 1 ({doc1.title}):")
    print(f"  Total units: {len(units1)}")
    for unit_type, count in sorted(types1.items(), key=lambda x: x[1], reverse=True):
        print(f"    • {unit_type}: {count}")

    # Analyze doc2 (GC/Sub meeting notes)
    units2 = decomposer.decompose(doc2.content, 'meeting_notes')
    types2 = {}
    for unit in units2:
        types2[unit.type] = types2.get(unit.type, 0) + 1

    print(f"\nSource 2 ({doc2.title}):")
    print(f"  Total units: {len(units2)}")
    for unit_type, count in sorted(types2.items(), key=lambda x: x[1], reverse=True):
        print(f"    • {unit_type}: {count}")

    # Strategy recommendation
    print("\n" + "="*80)
    print("INTEGRATION STRATEGY")
    print("="*80 + "\n")

    print("Analysis: The source documents contain user feedback and meeting notes")
    print("that don't map cleanly to the target document's product planning sections.\n")

    print("Recommended approach:")
    print("  1. Create a new section: '2.9 Recent Feedback & Updates'")
    print("  2. Add subsections for each source document")
    print("  3. Organize content by type (Feedback, Decisions, Action Items)")
    print("  4. You can then manually move items to their final sections\n")

    # Create structured content
    print("\n" + "="*80)
    print("GENERATING STRUCTURED CONTENT")
    print("="*80 + "\n")

    # Organize units by type
    def format_units_by_type(units, document_title):
        """Format units grouped by type."""
        output = []
        output.append(f"\n{document_title}\n{'─' * len(document_title)}\n")

        # Group by type
        by_type = {}
        for unit in units:
            if unit.type not in by_type:
                by_type[unit.type] = []
            by_type[unit.type].append(unit)

        # Order: action_item, decision, feature, metric, team_assignment, risk, timeline
        type_order = ['action_item', 'decision', 'feature', 'metric', 'team_assignment', 'risk', 'timeline']
        type_headings = {
            'action_item': 'Action Items',
            'decision': 'Decisions & Feedback',
            'feature': 'Feature Requests',
            'metric': 'Metrics & Observations',
            'team_assignment': 'Team Assignments',
            'risk': 'Risks & Concerns',
            'timeline': 'Timeline Items'
        }

        for unit_type in type_order:
            if unit_type in by_type:
                units_of_type = by_type[unit_type]
                output.append(f"\n{type_headings[unit_type]}\n")
                for i, unit in enumerate(units_of_type, 1):
                    prefix = {
                        'action_item': '→',
                        'decision': '✓',
                        'feature': '•',
                        'metric': '📊',
                        'team_assignment': '👤',
                        'risk': '⚠️',
                        'timeline': '📅'
                    }.get(unit_type, '•')

                    output.append(f"  {prefix} {unit.content}\n")

        return ''.join(output)

    # Generate formatted content
    section_content = """
2.9 Recent Feedback & Updates

This section consolidates recent user feedback and meeting notes from:
• Brokerflow Review (user feedback on prototype)
• GC/Subcontractor Flow Review Meeting (11/18/2025)

Review these items and move them to appropriate sections in the document as you address them.

"""

    section_content += format_units_by_type(units1, doc1.title)
    section_content += "\n\n"
    section_content += format_units_by_type(units2, doc2.title)

    # Show preview
    print("Content preview (first 2000 chars):")
    print("─" * 80)
    print(section_content[:2000])
    print("─" * 80)
    print(f"\nTotal content length: {len(section_content)} characters")
    print(f"Total semantic units: {len(units1) + len(units2)}")

    # Save to file for review
    output_file = Path(__file__).parent / "forsured_integration_content.txt"
    output_file.write_text(section_content)
    print(f"\n✅ Full content saved to: {output_file}")

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80 + "\n")

    print("1. Review the generated content in: forsured_integration_content.txt")
    print("2. Option A: Add this as a new section '2.9 Recent Feedback & Updates'")
    print("3. Option B: Manually integrate specific items into existing sections")
    print("4. Option C: Use the content integration system with a custom mapping\n")

    print("To add as a new section, I can:")
    print("  • Insert the content before 'Document Status'")
    print("  • Format it as a proper section with headings")
    print("  • Preserve all semantic units with proper categorization\n")

    print("="*80 + "\n")

    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
