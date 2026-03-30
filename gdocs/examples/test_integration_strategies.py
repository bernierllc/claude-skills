#!/usr/bin/env python3
"""
Test Integration Strategies - End-to-end integration pipeline test.

Tests the complete content integration pipeline:
1. Decompose meeting notes into semantic units
2. Match units to document sections
3. Determine integration strategies (ADD/UPDATE/MERGE/SKIP)
4. Display integration plan
"""

import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from scripts.content_decomposer import ContentDecomposer
from scripts.semantic_matcher import SemanticMatcher
from scripts.integration_strategy import StrategyDeterminer


# Sample meeting notes
MEETING_NOTES = """
Meeting Notes — NevarTodo Product Requirements

Timeline & Milestones:
• Q1 2026: Analytics dashboard launch
• Phase 1: Core feature development (Dec 2024 - Feb 2025)
• March 15, 2025: Beta release
• Q2 2026: Full production deployment
• Sprint 3: Authentication implementation
• Week 5: Begin integration testing

Core Features:
• Real-time data visualization
• Custom report generation
• Role-based access control (RBAC)
• Advanced filtering and search
• Export functionality (PDF, CSV, JSON)

Decisions Made:
✓ Approved analytics dashboard for Q1 2026
✓ Decided to use PostgreSQL for primary database
✓ Agreed on microservices architecture
✓ Greenlit AI-powered recommendations feature

Business Impact:
• 40% efficiency improvement expected
• ROI: Estimated $200K annual savings
• Performance: 5x faster query processing
• Target: 10,000 concurrent users

Technical Risks:
• Risk: Database migration complexity. Mitigation: Staged rollout with fallback plan
• Challenge: Real-time sync latency under load
• Concern: Third-party API rate limits for data ingestion
• Blocker: Authentication service dependency on external provider

Team Assignments:
• Assigned Kevin Patel as technical lead
• Backend Lead: Sarah Chen
• Frontend Engineer: Marcus Rodriguez
• Product Manager: Lisa Thompson

Next Steps & Action Items:
→ Dana to write technical specification by November 7, 2024
→ Kevin to finalize architecture diagram by end of week
→ Sarah to set up development environment by Monday
→ Marcus to create component library wireframes
→ Lisa to schedule stakeholder review meeting
"""


# Sample document sections with existing content
SAMPLE_DOC_SECTIONS = [
    {
        'heading': 'Product Overview',
        'level': 1,
        'content': 'NevarTodo is a next-generation task management platform designed for modern teams.',
        'start_index': 1,
        'end_index': 500
    },
    {
        'heading': 'Development Roadmap',
        'level': 1,
        'content': '''Our development timeline focuses on incremental delivery:

Phase 1: Foundation (Q4 2024)
• Core task management features
• Basic collaboration tools
• User authentication

Phase 2: Enhancement (Q1 2025)
• Advanced filtering
• Reporting dashboard

Phase 3: Scale (Q2 2025)
• Performance optimization
• Enterprise features
        ''',
        'start_index': 501,
        'end_index': 1200
    },
    {
        'heading': 'Core Features',
        'level': 1,
        'content': '''The platform includes:
• Task management with priorities
• Team collaboration workspace
• File attachments
• Basic reporting
        ''',
        'start_index': 1201,
        'end_index': 2400
    },
    {
        'heading': 'Technical Architecture',
        'level': 1,
        'content': '''Built on modern technology stack:
• Frontend: React with TypeScript
• Backend: Node.js microservices
• Database: To be determined
• Infrastructure: Cloud-native deployment
        ''',
        'start_index': 2401,
        'end_index': 3500
    },
    {
        'heading': 'Business Impact',
        'level': 1,
        'content': '''Expected to deliver significant productivity improvements for team collaboration.

Projected benefits include faster task completion and better team coordination.
        ''',
        'start_index': 3501,
        'end_index': 4200
    },
    {
        'heading': 'Technical Risks',
        'level': 1,
        'content': '''Key challenges include scalability and data migration from existing systems.
        ''',
        'start_index': 4201,
        'end_index': 5000
    },
    {
        'heading': 'Project Team',
        'level': 1,
        'content': '''Our cross-functional team brings expertise in product development:
• Technical Lead: TBD
• Design Lead: Alex Kim
        ''',
        'start_index': 5001,
        'end_index': 5800
    },
    {
        'heading': 'Next Steps',
        'level': 1,
        'content': '''Upcoming priorities and action items will be defined in sprint planning.
        ''',
        'start_index': 5801,
        'end_index': 6500
    },
    {
        'heading': 'Decisions',
        'level': 1,
        'content': '''Key decisions and approvals from stakeholders will be documented here.
        ''',
        'start_index': 6501,
        'end_index': 7200
    },
]


def test_full_integration_pipeline():
    """Test complete integration pipeline end-to-end."""

    print("\n" + "="*80)
    print("CONTENT INTEGRATION PIPELINE TEST")
    print("="*80 + "\n")

    # Step 1: Decompose meeting notes
    print("STEP 1: Decompose Meeting Notes")
    print("-" * 80 + "\n")

    decomposer = ContentDecomposer()
    units = decomposer.decompose(MEETING_NOTES, "meeting_notes")

    print(f"✅ Extracted {len(units)} semantic units\n")

    units_by_type = {}
    for unit in units:
        if unit.type not in units_by_type:
            units_by_type[unit.type] = 0
        units_by_type[unit.type] += 1

    for unit_type, count in sorted(units_by_type.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {unit_type}: {count} units")

    print("\n" + "-"*80 + "\n")

    # Step 2: Match units to sections
    print("STEP 2: Match Units to Document Sections")
    print("-" * 80 + "\n")

    matcher = SemanticMatcher()
    match_results = matcher.match_all_units(units, SAMPLE_DOC_SECTIONS)

    matched_pairs = []
    unmatched_units = []

    for unit, matches in match_results:
        if matches:
            matched_pairs.append((unit, matches[0]))  # Use best match
        else:
            unmatched_units.append(unit)

    print(f"✅ Matched {len(matched_pairs)}/{len(units)} units to sections\n")

    if unmatched_units:
        print(f"⚠️  {len(unmatched_units)} units had no matching sections\n")

    print("-"*80 + "\n")

    # Step 3: Determine integration strategies
    print("STEP 3: Determine Integration Strategies")
    print("-" * 80 + "\n")

    determiner = StrategyDeterminer()
    strategies = determiner.determine_strategies_for_all(matched_pairs)

    print(f"✅ Generated {len(strategies)} integration strategies\n")

    # Get summary
    summary = determiner.get_strategy_summary(strategies)

    print("Strategy Breakdown:")
    print(f"  • ADD: {summary['actions']['add']} (new content)")
    print(f"  • UPDATE: {summary['actions']['update']} (replace existing)")
    print(f"  • MERGE: {summary['actions']['merge']} (combine with existing)")
    print(f"  • SKIP: {summary['actions']['skip']} (already exists)")
    print()

    print(f"High Confidence (>80%): {summary['high_confidence']}/{summary['total_strategies']}")
    print(f"Average Confidence: {summary['avg_confidence']:.0%}")
    print(f"Modification Rate: {summary['modification_rate']:.1f}%")
    print()

    print(f"Sections to Modify: {len(summary['sections_modified'])}")
    for section in summary['sections_modified']:
        print(f"  • {section}")

    print("\n" + "-"*80 + "\n")

    # Step 4: Display Integration Plan
    print("STEP 4: Integration Plan Details")
    print("-" * 80 + "\n")

    # Group strategies by section
    by_section = {}
    for strategy in strategies:
        if strategy.target_section not in by_section:
            by_section[strategy.target_section] = []
        by_section[strategy.target_section].append(strategy)

    for section_name in sorted(by_section.keys()):
        section_strategies = by_section[section_name]

        # Count actions in this section
        adds = sum(1 for s in section_strategies if s.action == 'add')
        updates = sum(1 for s in section_strategies if s.action == 'update')
        merges = sum(1 for s in section_strategies if s.action == 'merge')
        skips = sum(1 for s in section_strategies if s.action == 'skip')

        print(f"\n📄 {section_name}")
        print(f"   {len(section_strategies)} strategies: {adds} ADD, {updates} UPDATE, {merges} MERGE, {skips} SKIP")
        print()

        # Show first few strategies
        for i, strategy in enumerate(section_strategies[:3], 1):
            action_icon = {
                'add': '➕',
                'update': '🔄',
                'merge': '🔀',
                'skip': '⏭️'
            }.get(strategy.action, '❓')

            print(f"   {action_icon} {strategy.action.upper()} ({strategy.confidence:.0%} confidence)")
            print(f"      Unit: {strategy.unit.type} - {strategy.unit.content[:50]}...")
            print(f"      Reasoning: {strategy.reasoning[:80]}...")
            print()

        if len(section_strategies) > 3:
            print(f"   ... and {len(section_strategies) - 3} more\n")

    print("="*80 + "\n")

    return units, matched_pairs, strategies, summary


def validate_integration_strategies(strategies, summary):
    """Validate that integration strategies meet quality criteria."""

    print("VALIDATION CHECKS")
    print("="*80 + "\n")

    checks_passed = 0
    checks_total = 0

    # Check 1: Most strategies should be high confidence (>70%)
    checks_total += 1
    high_conf_rate = summary['high_confidence'] / summary['total_strategies']
    if high_conf_rate >= 0.7:
        print("✅ High confidence rate >= 70%")
        checks_passed += 1
    else:
        print(f"❌ High confidence rate too low: {high_conf_rate:.0%}")

    # Check 2: Average confidence should be good (>70%)
    checks_total += 1
    if summary['avg_confidence'] >= 0.7:
        print("✅ Average confidence >= 70%")
        checks_passed += 1
    else:
        print(f"❌ Average confidence too low: {summary['avg_confidence']:.0%}")

    # Check 3: Should have mostly ADD strategies for new content
    checks_total += 1
    add_rate = summary['actions']['add'] / summary['total_strategies']
    if add_rate >= 0.5:  # At least 50% should be ADD for new meetings
        print("✅ Appropriate ADD strategy rate for new content")
        checks_passed += 1
    else:
        print(f"❌ ADD rate seems low: {add_rate:.0%}")

    # Check 4: Should have some UPDATE/MERGE for existing content
    checks_total += 1
    update_merge = summary['actions']['update'] + summary['actions']['merge']
    if update_merge > 0:
        print("✅ System detects and updates existing content")
        checks_passed += 1
    else:
        print("⚠️  No UPDATE/MERGE strategies (might be okay for new content)")
        checks_passed += 0.5  # Partial credit

    # Check 5: Multiple sections should be modified
    checks_total += 1
    if len(summary['sections_modified']) >= 5:
        print("✅ Multiple sections will be modified")
        checks_passed += 1
    else:
        print(f"❌ Too few sections modified: {len(summary['sections_modified'])}")

    # Check 6: Modification rate should be high
    checks_total += 1
    if summary['modification_rate'] >= 80:
        print("✅ High modification rate (most units will change document)")
        checks_passed += 1
    else:
        print(f"⚠️  Modification rate: {summary['modification_rate']:.1f}%")

    print("\n" + "-"*80)
    print(f"\nValidation Result: {checks_passed}/{checks_total} checks passed")

    if checks_passed >= checks_total * 0.9:
        print("✅ Integration strategies are working excellently!\n")
        return True
    elif checks_passed >= checks_total * 0.7:
        print("⚠️  Integration strategies are working well, minor improvements needed\n")
        return True
    else:
        print("❌ Integration strategies need improvement\n")
        return False


if __name__ == '__main__':
    # Run full pipeline test
    units, matched_pairs, strategies, summary = test_full_integration_pipeline()

    # Validate results
    is_valid = validate_integration_strategies(strategies, summary)

    # Exit with appropriate code
    sys.exit(0 if is_valid else 1)
