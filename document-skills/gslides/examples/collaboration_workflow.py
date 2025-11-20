#!/usr/bin/env python3
"""
Test: Collaboration Workflow
Phase: 6
Purpose: Demonstrate collaboration features with comments and attribution

This example shows:
1. Creating a multi-contributor presentation
2. Adding comments from different "reviewers"
3. Adding suggestions for improvements
4. Adding attribution slide for data sources
5. Tracking changes made by each contributor
6. Final presentation with full attribution
"""

import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.gslides_editor import GoogleSlidesEditor


def create_initial_presentation(editor: GoogleSlidesEditor) -> dict:
    """Create initial presentation (by Author 1)."""
    print("\n" + "="*70)
    print("CONTRIBUTOR 1: Creating initial presentation")
    print("="*70)

    result = editor.create_presentation('Q4 Product Roadmap - Collaborative Review')
    pres_id = result['pres_id']

    print(f"\n✓ Created presentation: {result['pres_url']}")

    # Slide 1: Title
    print("\nAdding Slide 1: Title...")
    slide1 = editor.create_slide(pres_id)
    editor.insert_text_box(
        pres_id, slide1['slide_id'],
        'Q4 Product Roadmap',
        x=50, y=150, width=620, height=80
    )

    # Slide 2: Current Challenges
    print("Adding Slide 2: Current Challenges...")
    slide2 = editor.create_slide(pres_id)
    editor.insert_text_box(
        pres_id, slide2['slide_id'],
        'Current Challenges',
        x=50, y=50, width=620, height=60
    )

    challenges = [
        'Performance: 3-5 second load times',
        'Mobile experience needs improvement',
        'Customer feedback: Feature complexity'
    ]

    y_pos = 130
    for challenge in challenges:
        editor.insert_text_box(
            pres_id, slide2['slide_id'],
            f'• {challenge}',
            x=80, y=y_pos, width=560, height=40
        )
        y_pos += 50

    # Slide 3: Proposed Solutions
    print("Adding Slide 3: Proposed Solutions...")
    slide3 = editor.create_slide(pres_id)
    editor.insert_text_box(
        pres_id, slide3['slide_id'],
        'Proposed Solutions',
        x=50, y=50, width=620, height=60
    )

    solutions = [
        'Implement caching layer (target: <1s load)',
        'Redesign mobile interface',
        'Simplify onboarding flow'
    ]

    y_pos = 130
    for solution in solutions:
        editor.insert_text_box(
            pres_id, slide3['slide_id'],
            f'• {solution}',
            x=80, y=y_pos, width=560, height=40
        )
        y_pos += 50

    # Slide 4: Timeline (with data)
    print("Adding Slide 4: Timeline with chart...")
    slide4 = editor.create_slide(pres_id)
    editor.insert_text_box(
        pres_id, slide4['slide_id'],
        'Implementation Timeline',
        x=50, y=30, width=620, height=50
    )

    # Add Gantt-style chart
    data = {
        'categories': ['Week 1-2', 'Week 3-4', 'Week 5-6', 'Week 7-8'],
        'series': [
            {'name': 'Performance', 'values': [100, 100, 50, 0]},
            {'name': 'Mobile', 'values': [0, 50, 100, 100]},
            {'name': 'Onboarding', 'values': [0, 0, 50, 100]}
        ]
    }
    position = {'x': 60, 'y': 100, 'width': 600, 'height': 280}
    editor.create_chart(pres_id, slide4['slide_id'], 'COLUMN_CHART', data, position)

    print("\n✓ Initial presentation created (4 slides)")

    return {
        'pres_id': pres_id,
        'pres_url': result['pres_url'],
        'slide_count': 4,
        'author': 'Product Manager',
        'timestamp': datetime.now().isoformat()
    }


def add_reviewer_comments(editor: GoogleSlidesEditor, pres_id: str):
    """Add comments from different reviewers."""
    print("\n\n" + "="*70)
    print("COLLABORATION: Adding reviewer comments")
    print("="*70)

    # Reviewer 1: Engineering Lead
    print("\n📝 REVIEWER 1 (Engineering Lead) - Technical Feedback:")
    print("-" * 70)

    comments = [
        {
            'slide_index': 2,
            'author': 'Engineering Lead',
            'text': 'The 3-5s load time is actually worst-case. Average is 2.5s. '
                   'Should we update to be more accurate?',
            'type': 'clarification'
        },
        {
            'slide_index': 3,
            'author': 'Engineering Lead',
            'text': 'Caching implementation will require Redis infrastructure. '
                   'Add note about infrastructure requirements?',
            'type': 'suggestion'
        },
        {
            'slide_index': 4,
            'author': 'Engineering Lead',
            'text': 'Timeline looks aggressive. Week 7-8 overlap might cause resource constraints. '
                   'Consider staggering mobile and onboarding work.',
            'type': 'concern'
        }
    ]

    for comment in comments:
        print(f"\n  Slide {comment['slide_index']} [{comment['type'].upper()}]:")
        print(f"  \"{comment['text']}\"")

        editor.add_comment(
            pres_id,
            slide_index=comment['slide_index'],
            text=comment['text'],
            author=comment['author']
        )

    print("\n  ✓ Added 3 comments from Engineering Lead")

    # Reviewer 2: Design Lead
    print("\n\n📝 REVIEWER 2 (Design Lead) - UX Feedback:")
    print("-" * 70)

    comments = [
        {
            'slide_index': 2,
            'author': 'Design Lead',
            'text': 'Customer feedback point is too vague. What specific features are complex? '
                   'We have data from user interviews.',
            'type': 'suggestion'
        },
        {
            'slide_index': 3,
            'author': 'Design Lead',
            'text': '"Redesign mobile interface" needs more detail. Scope unclear. '
                   'Are we talking about responsive tweaks or full native app?',
            'type': 'clarification'
        },
        {
            'slide_index': 3,
            'author': 'Design Lead',
            'text': '👍 Love the onboarding simplification! This addresses top user complaint.',
            'type': 'approval'
        }
    ]

    for comment in comments:
        print(f"\n  Slide {comment['slide_index']} [{comment['type'].upper()}]:")
        print(f"  \"{comment['text']}\"")

        editor.add_comment(
            pres_id,
            slide_index=comment['slide_index'],
            text=comment['text'],
            author=comment['author']
        )

    print("\n  ✓ Added 3 comments from Design Lead")

    # Reviewer 3: Executive Sponsor
    print("\n\n📝 REVIEWER 3 (Executive Sponsor) - Strategic Feedback:")
    print("-" * 70)

    comments = [
        {
            'slide_index': 1,
            'author': 'VP of Product',
            'text': 'Add subtitle clarifying this is Q4 2024 roadmap. Also mention target customer segment.',
            'type': 'suggestion'
        },
        {
            'slide_index': 4,
            'author': 'VP of Product',
            'text': 'Where are the success metrics? Need KPIs for each initiative. '
                   'How do we measure if caching actually improved load times?',
            'type': 'requirement'
        },
        {
            'slide_index': 4,
            'author': 'VP of Product',
            'text': 'Add data sources for timeline estimates. Are these based on velocity, '
                   'historical data, or engineering estimates?',
            'type': 'requirement'
        }
    ]

    for comment in comments:
        print(f"\n  Slide {comment['slide_index']} [{comment['type'].upper()}]:")
        print(f"  \"{comment['text']}\"")

        editor.add_comment(
            pres_id,
            slide_index=comment['slide_index'],
            text=comment['text'],
            author=comment['author']
        )

    print("\n  ✓ Added 3 comments from VP of Product")

    print("\n\n✓ Total comments added: 9 from 3 reviewers")


def incorporate_feedback(editor: GoogleSlidesEditor, pres_id: str):
    """Incorporate reviewer feedback into presentation."""
    print("\n\n" + "="*70)
    print("CONTRIBUTOR 2: Incorporating reviewer feedback")
    print("="*70)

    presentation = editor.get_presentation(pres_id)
    slides = presentation.get('slides', [])

    # Update 1: Add subtitle to title slide (VP request)
    print("\n✏️  Update 1: Adding subtitle to title slide")
    print("   Addressing: VP of Product feedback")
    slide1_id = slides[0]['objectId']
    editor.insert_text_box(
        pres_id, slide1_id,
        'Q4 2024 | Enterprise Customer Segment',
        x=50, y=240, width=620, height=40
    )
    print("   ✓ Added subtitle with quarter and segment")

    # Update 2: Clarify performance metric (Engineering request)
    print("\n✏️  Update 2: Updating performance metric")
    print("   Addressing: Engineering Lead feedback")
    slide2_id = slides[1]['objectId']
    editor.insert_text_box(
        pres_id, slide2_id,
        '   (avg: 2.5s, worst: 5s)',
        x=100, y=155, width=400, height=30
    )
    print("   ✓ Added average vs worst-case clarification")

    # Update 3: Add specific complexity examples (Design request)
    print("\n✏️  Update 3: Adding feature complexity details")
    print("   Addressing: Design Lead feedback")
    editor.insert_text_box(
        pres_id, slide2_id,
        '   Dashboard configuration, Advanced filters',
        x=100, y=235, width=500, height=30
    )
    print("   ✓ Added specific features from user interviews")

    # Update 4: Add scope clarification for mobile (Design request)
    print("\n✏️  Update 4: Clarifying mobile redesign scope")
    print("   Addressing: Design Lead feedback")
    slide3_id = slides[2]['objectId']
    editor.insert_text_box(
        pres_id, slide3_id,
        '   (Responsive web optimization, not native app)',
        x=100, y=185, width=500, height=30
    )
    print("   ✓ Added scope clarification")

    # Update 5: Add new slide for success metrics (VP requirement)
    print("\n✏️  Update 5: Adding success metrics slide")
    print("   Addressing: VP of Product requirement")
    metrics_slide = editor.create_slide(pres_id)

    editor.insert_text_box(
        pres_id, metrics_slide['slide_id'],
        'Success Metrics & KPIs',
        x=50, y=50, width=620, height=60
    )

    metrics = [
        'Performance: Load time <1s (from 2.5s avg)',
        'Mobile: Mobile conversion +25%',
        'Onboarding: Time-to-first-value <5min (from 15min)'
    ]

    y_pos = 130
    for metric in metrics:
        editor.insert_text_box(
            pres_id, metrics_slide['slide_id'],
            f'• {metric}',
            x=80, y=y_pos, width=560, height=40
        )
        y_pos += 50

    print("   ✓ Added new slide with KPIs for each initiative")

    # Update 6: Add infrastructure note (Engineering suggestion)
    print("\n✏️  Update 6: Adding infrastructure requirements note")
    print("   Addressing: Engineering Lead suggestion")
    editor.insert_text_box(
        pres_id, slide3_id,
        '   *Requires: Redis cluster, CDN setup',
        x=100, y=135, width=500, height=25
    )
    print("   ✓ Added infrastructure requirements")

    print("\n\n✓ Incorporated 6 updates based on reviewer feedback")


def add_attribution_slide(editor: GoogleSlidesEditor, pres_id: str):
    """Add comprehensive attribution for all data sources."""
    print("\n\n" + "="*70)
    print("CONTRIBUTOR 3: Adding attribution and data sources")
    print("="*70)

    print("\n📊 Adding data source attribution...")

    # Define all sources used in presentation
    sources = [
        {
            'title': 'Performance Monitoring Dashboard',
            'date': '2024-01-10',
            'url': 'https://internal.company.com/metrics/performance',
            'department': 'Engineering',
            'description': 'Load time metrics, avg and p95 values'
        },
        {
            'title': 'User Interview Study - Q4 2023',
            'date': '2023-12-15',
            'author': 'UX Research Team',
            'description': 'Customer feedback on feature complexity'
        },
        {
            'title': 'Mobile Analytics Report',
            'date': '2024-01-05',
            'url': 'https://analytics.company.com/mobile',
            'department': 'Product Analytics',
            'description': 'Mobile conversion rates and user behavior'
        },
        {
            'title': 'Engineering Team Velocity Data',
            'date': '2024-01-08',
            'department': 'Engineering',
            'description': 'Historical sprint velocity for timeline estimates'
        },
        {
            'title': 'Onboarding Funnel Analysis',
            'date': '2024-01-12',
            'url': 'https://analytics.company.com/onboarding',
            'department': 'Product Analytics',
            'description': 'Time-to-first-value measurements'
        }
    ]

    # Add attribution using editor method
    editor.add_attribution(pres_id, sources)

    print("\n  ✓ Added attribution for 5 data sources:")
    for i, source in enumerate(sources, 1):
        print(f"    {i}. {source['title']}")
        if 'url' in source:
            print(f"       URL: {source['url']}")
        if 'author' in source:
            print(f"       Author: {source['author']}")
        if 'department' in source:
            print(f"       Department: {source['department']}")

    print("\n\n✓ Attribution slide added to presentation")


def display_collaboration_summary(initial_result: dict):
    """Display summary of collaboration workflow."""
    print("\n\n" + "="*70)
    print("COLLABORATION WORKFLOW SUMMARY")
    print("="*70)

    print("\n📋 CONTRIBUTION TIMELINE:")
    print("-" * 70)

    timeline = [
        {
            'contributor': 'Product Manager',
            'action': 'Created initial presentation (4 slides)',
            'timestamp': 'Day 1, 9:00 AM'
        },
        {
            'contributor': 'Engineering Lead',
            'action': 'Added 3 technical review comments',
            'timestamp': 'Day 1, 2:00 PM'
        },
        {
            'contributor': 'Design Lead',
            'action': 'Added 3 UX review comments',
            'timestamp': 'Day 1, 3:30 PM'
        },
        {
            'contributor': 'VP of Product',
            'action': 'Added 3 strategic review comments',
            'timestamp': 'Day 1, 4:15 PM'
        },
        {
            'contributor': 'Product Manager',
            'action': 'Incorporated feedback (6 updates)',
            'timestamp': 'Day 2, 10:00 AM'
        },
        {
            'contributor': 'Data Analyst',
            'action': 'Added attribution for 5 data sources',
            'timestamp': 'Day 2, 11:30 AM'
        }
    ]

    for entry in timeline:
        print(f"\n  {entry['timestamp']}")
        print(f"  {entry['contributor']}: {entry['action']}")

    print("\n\n📊 COLLABORATION METRICS:")
    print("-" * 70)
    print(f"  Contributors:        5 people")
    print(f"  Comments Added:      9 total")
    print(f"  Updates Made:        6 incorporated")
    print(f"  Data Sources:        5 attributed")
    print(f"  Final Slide Count:   6 slides")
    print(f"  Review Cycles:       1 round")
    print(f"  Time to Completion:  2 days")

    print("\n\n💡 COLLABORATION INSIGHTS:")
    print("-" * 70)
    print("  ✓ Cross-functional input (Product, Engineering, Design, Executive)")
    print("  ✓ All reviewer concerns addressed")
    print("  ✓ Data sources properly attributed")
    print("  ✓ Technical feasibility validated")
    print("  ✓ Strategic alignment confirmed")
    print("  ✓ Ready for stakeholder presentation")

    print("\n\n🎯 COMMENT BREAKDOWN BY TYPE:")
    print("-" * 70)
    print("  Clarification Requests: 3")
    print("  Suggestions:            3")
    print("  Requirements:           2")
    print("  Approvals:              1")

    print(f"\n\n📄 Final Presentation: {initial_result['pres_url']}")


def main():
    """Run collaboration workflow demonstration."""
    print("\n" + "="*70)
    print("PHASE 6: COLLABORATION WORKFLOW")
    print("Demonstrating multi-contributor presentation development")
    print("="*70)

    # Initialize editor
    editor = GoogleSlidesEditor()

    # Step 1: Create initial presentation
    initial_result = create_initial_presentation(editor)
    pres_id = initial_result['pres_id']

    # Step 2: Add reviewer comments
    add_reviewer_comments(editor, pres_id)

    # Step 3: Incorporate feedback
    incorporate_feedback(editor, pres_id)

    # Step 4: Add attribution
    add_attribution_slide(editor, pres_id)

    # Step 5: Display summary
    display_collaboration_summary(initial_result)

    print("\n" + "="*70)
    print("✓ Collaboration Workflow Complete!")
    print("="*70)
    print("\nKey Takeaways:")
    print("  • Comments enable asynchronous collaboration")
    print("  • Attribution ensures data transparency and credibility")
    print("  • Structured feedback loops improve quality")
    print("  • Multi-contributor workflows create better presentations")
    print("  • Tracking changes maintains accountability")
    print("\n" + "="*70)


if __name__ == '__main__':
    main()
