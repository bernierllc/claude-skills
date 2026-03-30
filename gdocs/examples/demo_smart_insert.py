#!/usr/bin/env python3
"""
Demo: Smart AI-Powered Content Insertion

This demonstrates the difference between:
1. Basic insertion (just dump text at the end)
2. Smart insertion (context-aware, style-matching, preview)
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.smart_inserter import SmartInserter


def demo_basic_vs_smart():
    """Compare basic insertion vs smart insertion."""

    print("=" * 60)
    print("DEMO: Basic vs Smart Content Insertion")
    print("=" * 60)
    print()

    # Initialize
    editor = GoogleDocsEditor()
    smart = SmartInserter(editor)

    # Test document
    doc_url = "https://docs.google.com/document/d/1ggbKCrh8mQsS5XQb7lhKZye42bhm5hrwvX8HNfSiphE/edit"

    # Content to insert
    content = "Real-time collaboration features allow multiple users to edit simultaneously with live cursor tracking and presence indicators."
    intent = "feature description"

    print("📝 Content to insert:")
    print(f'   "{content}"')
    print()
    print(f"🎯 Intent: {intent}")
    print()
    print("=" * 60)
    print()

    # BASIC INSERTION (old way)
    print("❌ BASIC INSERTION (Old Way):")
    print("   1. Find end of document")
    print("   2. Insert text")
    print("   3. Apply blue color")
    print("   4. Done (no context, no style matching)")
    print()

    # SMART INSERTION (new way)
    print("✨ SMART INSERTION (New Way):")
    print()

    result = smart.smart_insert(
        doc_url=doc_url,
        content=content,
        intent=intent,
        target_section=None,  # Let AI decide
        auto_execute=False  # Just preview, don't execute yet
    )

    if result['success']:
        print()
        print("=" * 60)
        print("📊 ANALYSIS RESULTS:")
        print("=" * 60)
        print()

        context = result['context']
        print(f"Document Style Analysis:")
        print(f"  • Tone: {context.writing_style.get('tone')}")
        print(f"  • Voice: {context.writing_style.get('voice')}")
        print(f"  • Tense: {context.writing_style.get('tense')}")
        print(f"  • List preference: {context.writing_style.get('list_preference')}")
        print()

        print(f"Content Patterns Detected:")
        print(f"  • Has bullet lists: {context.existing_patterns.get('has_bullet_lists')}")
        print(f"  • Has numbered lists: {context.existing_patterns.get('has_numbered_lists')}")
        print(f"  • Has tables: {context.existing_patterns.get('has_tables')}")
        print()

        print("=" * 60)
        print("💡 RECOMMENDED STRATEGY:")
        print("=" * 60)
        print()

        strategy = result['recommended']
        print(f"Section: {strategy.section_name}")
        print(f"Position: {strategy.position_description}")
        print(f"Format: {strategy.format_type}")
        print(f"Confidence: {strategy.confidence:.0%}")
        print()
        print(f"Reasoning:")
        print(f"  {strategy.reasoning}")
        print()

    return result


def demo_smart_insert_with_execution():
    """Demonstrate smart insertion with actual execution."""

    print("\n" + "=" * 60)
    print("DEMO: Smart Insert with Auto-Execution")
    print("=" * 60)
    print()

    editor = GoogleDocsEditor()
    smart = SmartInserter(editor)

    doc_url = "https://docs.google.com/document/d/1ggbKCrh8mQsS5XQb7lhKZye42bhm5hrwvX8HNfSiphE/edit"

    # Different content types to test
    test_cases = [
        {
            'content': 'Offline mode allows users to work without internet connectivity, with automatic sync when connection is restored.',
            'intent': 'feature description',
            'target_section': 'Core Features'
        },
        {
            'content': 'Rate limiting implemented at API gateway level with Redis-backed token bucket algorithm.',
            'intent': 'technical implementation',
            'target_section': 'Technical Architecture'
        },
        {
            'content': 'Multi-factor authentication using TOTP (Time-based One-Time Password) with support for authenticator apps.',
            'intent': 'security feature',
            'target_section': 'Authentication & Security'
        }
    ]

    print(f"Testing {len(test_cases)} different insertion scenarios...")
    print()

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'─' * 60}")
        print(f"Test Case {i}: {test['intent']}")
        print('─' * 60)
        print()

        result = smart.smart_insert(
            doc_url=doc_url,
            content=test['content'],
            intent=test['intent'],
            target_section=test.get('target_section'),
            auto_execute=False  # Set to True to actually execute
        )

        if result['success']:
            strategy = result['recommended']
            print(f"✓ Would insert into: {strategy.section_name}")
            print(f"  Format: {strategy.format_type}")
            print(f"  Confidence: {strategy.confidence:.0%}")

            if len(result['strategies']) > 1:
                print(f"\n  Alternative options:")
                for alt in result['strategies'][1:3]:  # Show up to 2 alternatives
                    print(f"    • {alt.section_name} (confidence: {alt.confidence:.0%})")


if __name__ == '__main__':
    # Run basic vs smart comparison
    result = demo_basic_vs_smart()

    # Ask user if they want to see more examples
    print("\n" + "=" * 60)
    print()

    choice = input("Run additional test cases? (y/n): ").strip().lower()

    if choice == 'y':
        demo_smart_insert_with_execution()

    print()
    print("=" * 60)
    print("✅ Demo complete!")
    print("=" * 60)
    print()
    print("Key Improvements:")
    print("  ✓ Context-aware section selection")
    print("  ✓ Style matching (tone, voice, tense)")
    print("  ✓ Format detection (bullets, paragraphs, etc.)")
    print("  ✓ Confidence scoring")
    print("  ✓ Preview before execution")
    print("  ✓ Multiple strategy options")
    print()
    print("To use in production:")
    print("  from scripts.smart_inserter import SmartInserter")
    print("  smart = SmartInserter(editor)")
    print("  smart.smart_insert(doc_url, content, intent, auto_execute=True)")
