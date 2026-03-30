#!/usr/bin/env python3
"""
Test tabs support in Google Docs skill.

This script tests:
1. Extracting tab ID from URL
2. Getting document with tabs content
3. Targeting specific tab for content insertion
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.content_inserter import ContentInserter, MergeOptions


def test_tab_extraction():
    """Test extracting tab ID from URL."""
    print("=" * 60)
    print("TEST 1: Tab ID Extraction")
    print("=" * 60)

    # Test with tab parameter
    url_with_tab = "https://docs.google.com/document/d/ABC123/edit?tab=t.82ynznspwjyi"
    tab_id = GoogleDocsEditor.extract_tab_id(url_with_tab)
    print(f"URL: {url_with_tab}")
    print(f"Extracted tab ID: {tab_id}")
    assert tab_id == "t.82ynznspwjyi", "Failed to extract tab ID"
    print("✅ PASS\n")

    # Test without tab parameter
    url_without_tab = "https://docs.google.com/document/d/ABC123/edit"
    tab_id = GoogleDocsEditor.extract_tab_id(url_without_tab)
    print(f"URL: {url_without_tab}")
    print(f"Extracted tab ID: {tab_id}")
    assert tab_id is None, "Should return None when no tab parameter"
    print("✅ PASS\n")


def test_get_document_with_tabs(doc_url):
    """Test getting document with tabs content."""
    print("=" * 60)
    print("TEST 2: Get Document with Tabs")
    print("=" * 60)

    editor = GoogleDocsEditor()

    try:
        # Get document with tabs
        document = editor.get_document(doc_url, include_tabs_content=True)

        print(f"Document title: {document.get('title')}")
        print(f"Document ID: {document.get('documentId')}")

        tabs = document.get('tabs', [])
        print(f"Number of tabs: {len(tabs)}")

        if tabs:
            print("\nTabs found:")
            for i, tab in enumerate(tabs):
                tab_props = tab.get('tabProperties', {})
                tab_id = tab_props.get('tabId')
                tab_title = tab_props.get('title', 'Untitled')
                tab_index = tab_props.get('index')
                print(f"  {i+1}. {tab_title} (ID: {tab_id}, Index: {tab_index})")

                # Check for child tabs
                child_tabs = tab.get('childTabs', [])
                if child_tabs:
                    print(f"     └─ Has {len(child_tabs)} child tab(s)")

            print("✅ PASS\n")
        else:
            print("No tabs found (single-tab document)")
            print("✅ PASS (backward compatible)\n")

        return tabs

    except Exception as e:
        print(f"❌ FAIL: {e}\n")
        raise


def test_find_tab_by_id(doc_url):
    """Test finding specific tab by ID."""
    print("=" * 60)
    print("TEST 3: Find Tab by ID")
    print("=" * 60)

    editor = GoogleDocsEditor()

    # Extract tab ID from URL
    tab_id = editor.extract_tab_id(doc_url)

    if tab_id:
        print(f"Tab ID from URL: {tab_id}")

        # Get document
        document = editor.get_document(doc_url, include_tabs_content=True)
        tabs = document.get('tabs', [])

        # Find specific tab
        target_tab = editor.find_tab_by_id(tabs, tab_id)

        if target_tab:
            tab_title = target_tab.get('tabProperties', {}).get('title', 'Untitled')
            print(f"Found tab: {tab_title}")
            print("✅ PASS\n")
        else:
            print(f"❌ FAIL: Could not find tab with ID {tab_id}\n")
            raise ValueError(f"Tab not found: {tab_id}")
    else:
        print("No tab ID in URL (will use first tab by default)")
        print("✅ PASS\n")


def test_get_tab_body(doc_url):
    """Test getting body from specific tab."""
    print("=" * 60)
    print("TEST 4: Get Tab Body")
    print("=" * 60)

    editor = GoogleDocsEditor()

    # Extract tab ID
    tab_id = editor.extract_tab_id(doc_url)

    # Get document
    document = editor.get_document(doc_url, include_tabs_content=True)

    # Get body from target tab
    body = editor.get_tab_body(document, tab_id)

    print(f"Retrieved body from tab: {tab_id or 'first tab (default)'}")
    content_elements = body.get('content', [])
    print(f"Content elements: {len(content_elements)}")

    if content_elements:
        print("✅ PASS\n")
    else:
        print("⚠️  WARNING: No content in tab body\n")


def test_merge_with_tab(doc_url):
    """Test merging content with tab support."""
    print("=" * 60)
    print("TEST 5: Merge Content with Tab Support")
    print("=" * 60)

    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)

    # Extract tab ID to show it's being used
    tab_id = editor.extract_tab_id(doc_url)
    print(f"Tab ID from URL: {tab_id or 'None (will use first tab)'}")

    # Test content
    test_content = "🧪 Test content from tabs support test"

    try:
        result = inserter.merge_content(
            doc_url=doc_url,
            content=test_content,
            section=None,  # Insert at end
            options=MergeOptions(
                preserve_comments=True,
                add_source_comment=True,
                add_inline_attribution=True,
                source_description="tabs support test, 10/31/25"
            )
        )

        if result['success']:
            print("✅ PASS: Content merged successfully\n")
            print(f"Insertion index: {result['insertion_point'].index}")
            print(f"Message: {result['message']}")
        else:
            print(f"❌ FAIL: {result.get('message', 'Unknown error')}\n")
            raise ValueError("Merge failed")

    except Exception as e:
        print(f"❌ FAIL: {e}\n")
        raise


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("GOOGLE DOCS TABS SUPPORT TEST SUITE")
    print("=" * 60 + "\n")

    # Test 1: Tab extraction (no doc needed)
    test_tab_extraction()

    # Ask for document URL
    print("Please provide a Google Docs URL to test with:")
    print("(Ideally a document with multiple tabs)")
    doc_url = input("URL: ").strip()

    if not doc_url:
        print("No URL provided. Exiting.")
        return

    # Run tests that need a document
    try:
        tabs = test_get_document_with_tabs(doc_url)
        test_find_tab_by_id(doc_url)
        test_get_tab_body(doc_url)

        # Only test merge if user confirms
        if tabs and len(tabs) > 1:
            print("\n⚠️  This document has multiple tabs.")
            print("The next test will INSERT test content into the document.")
            response = input("Proceed with merge test? (y/n): ").strip().lower()
            if response == 'y':
                test_merge_with_tab(doc_url)
            else:
                print("Skipping merge test.")
        else:
            print("\n⚠️  Single-tab document detected.")
            response = input("Proceed with merge test? (y/n): ").strip().lower()
            if response == 'y':
                test_merge_with_tab(doc_url)
            else:
                print("Skipping merge test.")

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED SUCCESSFULLY! 🎉")
        print("=" * 60)

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"TEST SUITE FAILED: {e}")
        print("=" * 60)
        sys.exit(1)


if __name__ == '__main__':
    main()
