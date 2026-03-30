#!/usr/bin/env python3
"""
Complete Pipeline Test - End-to-end content integration demonstration.

Tests the entire content integration pipeline from raw meeting notes
to executed document changes:

1. Decompose content into semantic units
2. Match units to document sections
3. Determine integration strategies
4. Generate diff preview
5. Execute changes (dry run)
"""

import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from scripts.content_decomposer import ContentDecomposer
from scripts.semantic_matcher import SemanticMatcher
from scripts.integration_strategy import StrategyDeterminer
from scripts.diff_generator import DiffGenerator
from scripts.integration_executor import IntegrationExecutor


# Sample meeting notes
MEETING_NOTES = """
Meeting Notes — NevarTodo Product Requirements

Timeline & Milestones:
• Q1 2026: Analytics dashboard launch
• Phase 1: Core feature development (Dec 2024 - Feb 2025)

Core Features:
• Real-time data visualization
• Custom report generation
• Role-based access control (RBAC)

Decisions Made:
✓ Approved analytics dashboard for Q1 2026
✓ Decided to use PostgreSQL for primary database

Business Impact:
• 40% efficiency improvement expected
• ROI: Estimated $200K annual savings

Team Assignments:
• Assigned Kevin Patel as technical lead
• Backend Lead: Sarah Chen

Next Steps:
→ Dana to write technical specification by November 7, 2024
→ Kevin to finalize architecture diagram by end of week
"""


# Sample document sections (simplified)
SAMPLE_DOC_SECTIONS = [
    {
        'heading': 'Development Roadmap',
        'level': 1,
        'content': '''Phase 1: Foundation (Q4 2024)
• Core task management features
• User authentication''',
        'start_index': 501,
        'end_index': 1200
    },
    {
        'heading': 'Core Features',
        'level': 1,
        'content': '''• Task management
• Team collaboration''',
        'start_index': 1201,
        'end_index': 2400
    },
    {
        'heading': 'Decisions',
        'level': 1,
        'content': '''Key decisions will be documented here.''',
        'start_index': 6501,
        'end_index': 7200
    },
    {
        'heading': 'Business Impact',
        'level': 1,
        'content': '''Expected productivity improvements.''',
        'start_index': 3501,
        'end_index': 4200
    },
    {
        'heading': 'Project Team',
        'level': 1,
        'content': '''• Technical Lead: TBD
• Design Lead: Alex Kim''',
        'start_index': 5001,
        'end_index': 5800
    },
    {
        'heading': 'Next Steps',
        'level': 1,
        'content': '''Action items will be defined.''',
        'start_index': 5801,
        'end_index': 6500
    },
]


def main():
    """Run complete pipeline test."""

    print("\n" + "🚀 " + "="*76 + " 🚀")
    print("                  COMPLETE CONTENT INTEGRATION PIPELINE")
    print("="*80 + "\n")

    # ========== STEP 1: DECOMPOSE ==========
    print("📋 STEP 1: Content Decomposition")
    print("-" * 80)

    decomposer = ContentDecomposer()
    units = decomposer.decompose(MEETING_NOTES, "meeting_notes")

    print(f"✅ Extracted {len(units)} semantic units from meeting notes")

    units_by_type = {}
    for unit in units:
        units_by_type[unit.type] = units_by_type.get(unit.type, 0) + 1

    for unit_type, count in sorted(units_by_type.items(), key=lambda x: x[1], reverse=True):
        print(f"   • {unit_type}: {count} units")

    print()

    # ========== STEP 2: MATCH ==========
    print("🎯 STEP 2: Semantic Matching")
    print("-" * 80)

    matcher = SemanticMatcher()
    match_results = matcher.match_all_units(units, SAMPLE_DOC_SECTIONS)

    matched_pairs = [(unit, matches[0]) for unit, matches in match_results if matches]

    print(f"✅ Matched {len(matched_pairs)}/{len(units)} units to sections")
    print(f"   Average match confidence: {sum(m[1].confidence for m in matched_pairs) / len(matched_pairs):.0%}")
    print()

    # ========== STEP 3: STRATEGY ==========
    print("💡 STEP 3: Integration Strategy Determination")
    print("-" * 80)

    determiner = StrategyDeterminer()
    strategies = determiner.determine_strategies_for_all(matched_pairs)

    strategy_summary = determiner.get_strategy_summary(strategies)

    print(f"✅ Generated {len(strategies)} integration strategies")
    print(f"   • ADD: {strategy_summary['actions']['add']}")
    print(f"   • UPDATE: {strategy_summary['actions']['update']}")
    print(f"   • MERGE: {strategy_summary['actions']['merge']}")
    print(f"   • SKIP: {strategy_summary['actions']['skip']}")
    print(f"   Average confidence: {strategy_summary['avg_confidence']:.0%}")
    print()

    # ========== STEP 4: DIFF PREVIEW ==========
    print("🔍 STEP 4: Diff Preview Generation")
    print("-" * 80 + "\n")

    generator = DiffGenerator()
    diff_entries = generator.generate_diff(strategies)

    # Show interactive preview
    preview = generator.generate_interactive_preview(diff_entries)
    print(preview)

    # ========== STEP 5: EXECUTION ==========
    print("⚙️  STEP 5: Execution (Dry Run)")
    print("-" * 80)

    executor = IntegrationExecutor(dry_run=True)

    # Validate first
    print("Validating strategies...")
    validation_errors = executor.validate_strategies(strategies)

    if validation_errors:
        print(f"❌ Validation failed:")
        for error in validation_errors:
            print(f"   • {error}")
        return False

    print("✅ All strategies validated")
    print()

    # Create execution plan
    print("Creating execution plan...")
    plan = executor.create_execution_plan(strategies)

    print(f"✅ Execution plan created:")
    print(f"   • Total operations: {plan.total_operations}")
    print(f"   • Estimated duration: {plan.estimated_duration:.2f}s")
    print()

    # Execute (dry run)
    print("Executing changes (dry run)...")
    result = executor.execute(strategies)

    print()
    if result.success:
        print("✅ EXECUTION SUCCESSFUL")
    else:
        print("❌ EXECUTION FAILED")

    print(f"   • Units processed: {result.units_processed}")
    print(f"   • Actions executed: {result.actions_executed}")
    print(f"   • Actions skipped: {result.actions_skipped}")
    print(f"   • Sections modified: {len(result.sections_modified)}")
    print(f"   • Execution time: {result.execution_time:.3f}s")

    if result.errors:
        print(f"\n   ⚠️  Errors encountered:")
        for error in result.errors:
            print(f"      • {error}")

    print()

    # ========== SUMMARY ==========
    print("=" * 80)
    print("📊 PIPELINE SUMMARY")
    print("=" * 80 + "\n")

    print(f"Input: {len(MEETING_NOTES.split())} words of meeting notes")
    print(f"Output: {result.actions_executed} changes applied to {len(result.sections_modified)} sections")
    print()

    print("Sections Modified:")
    for i, section in enumerate(sorted(result.sections_modified), 1):
        section_strategies = [s for s in strategies if s.target_section == section and s.action != 'skip']
        print(f"   {i}. {section} ({len(section_strategies)} changes)")

    print()
    print("Processing Time: {:.3f}s".format(
        result.execution_time
    ))

    print()
    print("=" * 80)
    print("✨ PIPELINE TEST COMPLETE ✨")
    print("=" * 80 + "\n")

    return result.success


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
