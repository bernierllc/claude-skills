#!/usr/bin/env python3
"""
Test Semantic Matcher with Real Document

Tests the semantic matcher by:
1. Decomposing meeting notes into semantic units
2. Getting sections from actual Google Doc
3. Matching units to sections
4. Displaying results with confidence scores
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import scripts package
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from scripts.semantic_units import SemanticUnit
from scripts.content_decomposer import ContentDecomposer
from scripts.semantic_matcher import SemanticMatcher, test_matcher_with_document


# Sample meeting notes (from NevarTodo project discussions)
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


# Sample document sections (simulating Google Doc structure)
SAMPLE_DOC_SECTIONS = [
    {
        'heading': 'Product Overview',
        'level': 1,
        'content': 'NevarTodo is a next-generation task management platform...',
        'start_index': 1,
        'end_index': 500
    },
    {
        'heading': 'Development Roadmap',
        'level': 1,
        'content': 'Our development timeline focuses on incremental delivery...',
        'start_index': 501,
        'end_index': 1200
    },
    {
        'heading': 'Core Features',
        'level': 1,
        'content': 'The platform includes task management, team collaboration...',
        'start_index': 1201,
        'end_index': 2400
    },
    {
        'heading': 'Technical Architecture',
        'level': 1,
        'content': 'Built on microservices architecture with React frontend...',
        'start_index': 2401,
        'end_index': 3500
    },
    {
        'heading': 'Business Impact',
        'level': 1,
        'content': 'Expected to deliver significant productivity improvements...',
        'start_index': 3501,
        'end_index': 4200
    },
    {
        'heading': 'Technical Risks',
        'level': 1,
        'content': 'Key challenges include scalability and data migration...',
        'start_index': 4201,
        'end_index': 5000
    },
    {
        'heading': 'Project Team',
        'level': 1,
        'content': 'Our cross-functional team brings expertise in...',
        'start_index': 5001,
        'end_index': 5800
    },
    {
        'heading': 'Next Steps',
        'level': 1,
        'content': 'Upcoming priorities and action items...',
        'start_index': 5801,
        'end_index': 6500
    },
    {
        'heading': 'Decisions',
        'level': 1,
        'content': 'Key decisions and approvals from stakeholders...',
        'start_index': 6501,
        'end_index': 7200
    },
]


def test_with_sample_data():
    """Test semantic matcher with sample meeting notes and document sections."""

    print("\n" + "="*80)
    print("SEMANTIC MATCHER TEST")
    print("="*80 + "\n")

    # Step 1: Decompose meeting notes
    print("Step 1: Decomposing meeting notes into semantic units...\n")
    decomposer = ContentDecomposer()
    units = decomposer.decompose(MEETING_NOTES, "meeting_notes")

    print(f"✅ Extracted {len(units)} semantic units from meeting notes\n")

    # Show unit breakdown by type
    units_by_type = {}
    for unit in units:
        if unit.type not in units_by_type:
            units_by_type[unit.type] = 0
        units_by_type[unit.type] += 1

    print("Unit breakdown:")
    for unit_type, count in sorted(units_by_type.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {unit_type}: {count} units")

    print("\n" + "-"*80 + "\n")

    # Step 2: Match units to document sections
    print("Step 2: Matching semantic units to document sections...\n")
    print(f"Document has {len(SAMPLE_DOC_SECTIONS)} sections:\n")
    for section in SAMPLE_DOC_SECTIONS:
        print(f"  • {section['heading']}")

    print("\n" + "-"*80 + "\n")

    # Step 3: Run semantic matcher
    print("Step 3: Running semantic matcher...\n")
    matcher = SemanticMatcher()
    results, summary = test_matcher_with_document(units, SAMPLE_DOC_SECTIONS)

    # Print detailed summary
    print("\n" + "="*80)
    print("MATCHING VALIDATION")
    print("="*80 + "\n")

    print(f"Match Rate: {summary['match_rate']:.1f}%")
    print(f"High Confidence Matches (>70%): {summary['high_confidence_matches']}/{summary['total_units']}")
    print(f"Average Confidence: {summary['avg_confidence']:.0%}")
    print(f"Sections Modified: {len(summary['sections_modified'])}")

    if summary['unmatched_units'] > 0:
        print(f"\n⚠️  Warning: {summary['unmatched_units']} units had no matching sections")

    print("\n" + "="*80 + "\n")

    return units, results, summary


def validate_matcher_accuracy(results, summary):
    """Validate that matcher produces sensible results."""

    print("VALIDATION CHECKS:")
    print("-" * 80 + "\n")

    checks_passed = 0
    checks_total = 0

    # Check 1: Match rate should be high (>80%)
    checks_total += 1
    if summary['match_rate'] >= 80:
        print("✅ Match rate >= 80%")
        checks_passed += 1
    else:
        print(f"❌ Match rate too low: {summary['match_rate']:.1f}%")

    # Check 2: Average confidence should be reasonable (>60%)
    checks_total += 1
    if summary['avg_confidence'] >= 0.6:
        print("✅ Average confidence >= 60%")
        checks_passed += 1
    else:
        print(f"❌ Average confidence too low: {summary['avg_confidence']:.0%}")

    # Check 3: Should have high confidence matches
    checks_total += 1
    if summary['high_confidence_matches'] >= summary['total_units'] * 0.5:
        print("✅ >50% of matches are high confidence")
        checks_passed += 1
    else:
        print(f"❌ Too few high confidence matches: {summary['high_confidence_matches']}")

    # Check 4: Should modify multiple sections
    checks_total += 1
    if len(summary['sections_modified']) >= 3:
        print("✅ Multiple sections will be modified")
        checks_passed += 1
    else:
        print(f"❌ Too few sections modified: {len(summary['sections_modified'])}")

    # Check 5: Verify type-specific matching examples
    checks_total += 1
    timeline_to_roadmap = False
    feature_to_features = False

    for unit, matches in results:
        if matches:
            best_match = matches[0]
            if unit.type == 'timeline' and 'roadmap' in best_match.section_name.lower():
                timeline_to_roadmap = True
            if unit.type == 'feature' and 'features' in best_match.section_name.lower():
                feature_to_features = True

    if timeline_to_roadmap and feature_to_features:
        print("✅ Type-based matching working correctly")
        checks_passed += 1
    else:
        print("❌ Type-based matching not working as expected")

    print("\n" + "-"*80)
    print(f"\nValidation Result: {checks_passed}/{checks_total} checks passed")

    if checks_passed == checks_total:
        print("✅ Semantic matcher is working correctly!\n")
        return True
    elif checks_passed >= checks_total * 0.8:
        print("⚠️  Semantic matcher is mostly working, but needs tuning\n")
        return True
    else:
        print("❌ Semantic matcher needs significant improvements\n")
        return False


if __name__ == '__main__':
    # Run test
    units, results, summary = test_with_sample_data()

    # Validate results
    is_valid = validate_matcher_accuracy(results, summary)

    # Exit with appropriate code
    sys.exit(0 if is_valid else 1)
