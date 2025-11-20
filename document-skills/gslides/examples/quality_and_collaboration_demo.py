#!/usr/bin/env python3
"""
Quality & Collaboration Demo

Demonstrates Phase 6 features:
- Comprehensive quality checking across 4 dimensions
- Comment and suggestion management
- Source attribution
- Change tracking

This example shows a complete workflow from creation to quality validation.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gslides_editor import GSlidesEditor
from scripts.quality_checker import QualityChecker
from scripts.comment_manager import CommentManager, Attribution


def main():
    """Run quality and collaboration demo."""
    # Get credentials
    credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
    anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')

    if not os.path.exists(credentials_path):
        print(f"Error: Credentials file not found at {credentials_path}")
        print("Set GOOGLE_CREDENTIALS_PATH environment variable")
        return

    print("Quality & Collaboration Demo")
    print("=" * 60)

    # Initialize services
    print("\n1. Initializing services...")
    editor = GSlidesEditor(credentials_path=credentials_path)

    # Create sample presentation
    print("\n2. Creating sample presentation...")
    presentation_id = editor.create_presentation("Quality Demo Presentation")
    print(f"   Created presentation: {presentation_id}")

    # Add some sample slides
    print("\n3. Adding sample content...")
    editor.add_slide(
        presentation_id,
        layout_type='TITLE_AND_BODY',
        title="Introduction",
        body="Welcome to our quality demonstration."
    )

    editor.add_slide(
        presentation_id,
        layout_type='TITLE_AND_BODY',
        title="Main Content",
        body="This slide contains the main content points."
    )

    editor.add_slide(
        presentation_id,
        layout_type='TITLE_ONLY',
        title="Conclusion"
    )

    # Initialize quality checker
    print("\n4. Running quality checks...")
    checker = QualityChecker(
        slides_service=editor.slides_service,
        anthropic_api_key=anthropic_api_key
    )

    # Run comprehensive quality check
    print("\n   Running comprehensive quality check...")
    report = checker.run_comprehensive_check(presentation_id)

    print(f"\n   Overall Quality Score: {report.overall_score:.1f}/100")
    print(f"\n   Dimension Scores:")
    print(f"   - Design:     {report.design_report.score:.1f}/100")
    print(f"   - Content:    {report.content_report.score:.1f}/100")
    print(f"   - Technical:  {report.technical_report.score:.1f}/100")
    print(f"   - Functional: {report.functional_report.score:.1f}/100")

    # Show priority issues
    if report.priority_fixes:
        print(f"\n   Priority Issues ({len(report.priority_fixes)} total):")
        for i, issue in enumerate(report.priority_fixes[:5], 1):
            print(f"   {i}. [{issue.severity.upper()}] {issue.description}")
            if issue.recommendation:
                print(f"      → {issue.recommendation}")
    else:
        print("\n   No critical issues found!")

    # Initialize comment manager
    print("\n5. Managing collaboration features...")
    comment_manager = CommentManager(
        slides_service=editor.slides_service,
        drive_service=editor.drive_service
    )

    # Add comments for quality issues
    print("\n   Adding improvement comments...")
    if report.priority_fixes:
        for issue in report.priority_fixes[:3]:
            if issue.severity == "critical":
                comment = comment_manager.add_comment(
                    presentation_id,
                    slide_index=0,
                    text=f"{issue.description}\n\nRecommendation: {issue.recommendation or 'Review and fix'}",
                    author="Quality Checker"
                )
                print(f"   - Added comment: {comment.text[:50]}...")

    # Add design suggestions
    print("\n   Adding design suggestions...")
    suggestion = comment_manager.add_suggestion(
        presentation_id,
        element_id="unknown",  # Would use actual element ID in real scenario
        suggestion="Consider using larger fonts for better readability",
        author="Design Reviewer"
    )
    print(f"   - Added suggestion: {suggestion.text}")

    # Add source attributions
    print("\n6. Adding source attributions...")
    sources = [
        Attribution(
            source="Google Slides API Documentation",
            author="Google",
            date="2024",
            url="https://developers.google.com/slides",
            description="API reference and best practices"
        ),
        Attribution(
            source="Claude AI",
            author="Anthropic",
            url="https://claude.ai",
            description="AI-powered content generation and quality analysis"
        ),
        Attribution(
            source="WCAG 2.1 Guidelines",
            author="W3C",
            date="2018",
            url="https://www.w3.org/WAI/WCAG21/",
            description="Web accessibility standards"
        )
    ]

    comment_manager.add_attribution(presentation_id, sources, method='slide')
    print(f"   Added {len(sources)} source attributions")

    # Track changes
    print("\n7. Tracking changes...")
    comment_manager.track_changes(
        presentation_id,
        author="Quality Demo Script",
        change_description="Created presentation with sample content, ran quality checks, added comments and attributions"
    )
    print("   Change log updated")

    # List all comments
    print("\n8. Reviewing all comments...")
    all_comments = comment_manager.list_comments(presentation_id)
    print(f"   Total comments: {len(all_comments)}")
    for i, comment in enumerate(all_comments[:3], 1):
        print(f"   {i}. [{comment.author}] {comment.text[:60]}...")

    # Generate quality report summary
    print("\n" + "=" * 60)
    print("QUALITY REPORT SUMMARY")
    print("=" * 60)

    print(f"\nPresentation ID: {presentation_id}")
    print(f"Overall Quality: {report.overall_score:.1f}/100")

    if report.overall_score >= 90:
        quality_level = "EXCELLENT"
    elif report.overall_score >= 80:
        quality_level = "GOOD"
    elif report.overall_score >= 70:
        quality_level = "ACCEPTABLE"
    else:
        quality_level = "NEEDS IMPROVEMENT"

    print(f"Quality Level: {quality_level}")

    print("\nDetailed Scores:")
    print(f"  Design Quality:     {report.design_report.score:.1f}/100")
    print(f"    - Contrast:       {report.design_report.contrast_ratios or 'N/A'}")
    print(f"    - Hierarchy:      {report.design_report.hierarchy_score:.1f}")
    print(f"    - Whitespace:     {report.design_report.whitespace_score:.1f}")
    print(f"    - Alignment:      {report.design_report.alignment_score:.1f}")

    print(f"\n  Content Quality:    {report.content_report.score:.1f}/100")
    print(f"    - Grammar:        {report.content_report.grammar_score:.1f}")
    print(f"    - Clarity:        {report.content_report.clarity_score:.1f}")
    print(f"    - Audience Fit:   {report.content_report.audience_score:.1f}")
    print(f"    - Story Arc:      {report.content_report.story_arc_score:.1f}")

    print(f"\n  Technical Quality:  {report.technical_report.score:.1f}/100")
    print(f"    - Images:         {report.technical_report.image_quality_score:.1f}")
    print(f"    - Fonts:          {report.technical_report.font_availability_score:.1f}")
    print(f"    - Links:          {report.technical_report.link_validity_score:.1f}")
    print(f"    - Objects:        {report.technical_report.object_integrity_score:.1f}")

    print(f"\n  Functional Quality: {report.functional_report.score:.1f}/100")
    print(f"    - Slide Count:    {report.functional_report.slide_count_score:.1f}")
    print(f"    - Reading Level:  {report.functional_report.reading_level_score:.1f}")
    print(f"    - Accessibility:  {report.functional_report.accessibility_score:.1f}")
    print(f"    - Compatibility:  {report.functional_report.compatibility_score:.1f}")

    print("\nRecommendations:")
    all_recommendations = (
        report.design_report.recommendations +
        report.content_report.recommendations +
        report.technical_report.recommendations +
        report.functional_report.recommendations
    )

    if all_recommendations:
        for i, rec in enumerate(all_recommendations[:5], 1):
            print(f"  {i}. {rec}")
    else:
        print("  None - presentation meets quality standards!")

    print("\n" + "=" * 60)
    print(f"\nView presentation: https://docs.google.com/presentation/d/{presentation_id}")
    print("\nDemo complete!")


if __name__ == '__main__':
    main()
