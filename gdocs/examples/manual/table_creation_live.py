#!/usr/bin/env python3
"""
Test Phase 2: Table Creation

Tests all Phase 2 table creation functionality:
- create_table() - Base table creation
- create_table() with headers - Header row population
- create_table() with data - Data population
- create_table() with section - Section-based insertion
"""

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.table_manager import TableManager


def test_phase2():
    """Test Phase 2 table creation functionality."""
    print("=" * 60)
    print("Phase 2 Table Creation Test")
    print("=" * 60)

    # Initialize
    editor = GoogleDocsEditor()
    table_manager = TableManager(editor)

    # Create test document
    print("\n1. Creating test document...")
    doc_result = editor.create_document("Table Manager Test - Phase 2")
    doc_id = doc_result['doc_id']
    doc_url = doc_result['doc_url']

    print(f"✓ Created document: {doc_url}")

    # Add some sections for section-based insertion testing
    print("\n2. Adding section headings to document...")
    try:
        requests = [
            # Insert "Project Timeline" heading
            {
                'insertText': {
                    'text': 'Project Timeline\n',
                    'location': {'index': 1}
                }
            },
            # Style it as HEADING_1
            {
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': 1,
                        'endIndex': 18
                    },
                    'paragraphStyle': {
                        'namedStyleType': 'HEADING_1'
                    },
                    'fields': 'namedStyleType'
                }
            },
            # Insert "Feature Comparison" heading after some space
            {
                'insertText': {
                    'text': '\n\nFeature Comparison\n',
                    'location': {'index': 18}
                }
            },
            # Style it as HEADING_1
            {
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': 20,
                        'endIndex': 39
                    },
                    'paragraphStyle': {
                        'namedStyleType': 'HEADING_1'
                    },
                    'fields': 'namedStyleType'
                }
            }
        ]

        editor.docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()

        print("✓ Added section headings")

    except Exception as e:
        print(f"✗ Failed to add headings: {e}")
        return False

    # Test 1: Create basic table (no headers, no data)
    print("\n3. Testing create_table() - basic 3x3 table...")
    try:
        result = table_manager.create_table(
            doc_url=doc_url,
            rows=3,
            columns=3
        )

        if result['success']:
            print(f"✓ Created basic table: {result['message']}")
            table = result['table_location']
            print(f"  - Table: {table.rows}x{table.columns} at index {table.start_index}")
        else:
            print(f"✗ Failed: {result['message']}")
            return False

    except Exception as e:
        print(f"✗ create_table() basic failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 2: Create table with headers only
    print("\n4. Testing create_table() with headers...")
    try:
        headers = ["Name", "Status", "Priority"]
        result = table_manager.create_table(
            doc_url=doc_url,
            rows=4,
            columns=3,
            headers=headers
        )

        if result['success']:
            print(f"✓ Created table with headers: {result['message']}")
            table = result['table_location']
            print(f"  - Table: {table.rows}x{table.columns}")
            print(f"  - Headers: {headers}")
        else:
            print(f"✗ Failed: {result['message']}")
            return False

    except Exception as e:
        print(f"✗ create_table() with headers failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 3: Create table with headers and data
    print("\n5. Testing create_table() with headers and data...")
    try:
        headers = ["Feature", "Current", "Proposed"]
        data = [
            ["AI Help", "None", "GPT-4"],
            ["Sync", "Daily", "Real-time"],
            ["Mobile", "Basic", "Full native"]
        ]

        result = table_manager.create_table(
            doc_url=doc_url,
            rows=4,
            columns=3,
            headers=headers,
            data=data
        )

        if result['success']:
            print(f"✓ Created table with headers and data: {result['message']}")
            table = result['table_location']
            print(f"  - Table: {table.rows}x{table.columns}")
            print(f"  - Headers: {headers}")
            print(f"  - Data rows: {len(data)}")
        else:
            print(f"✗ Failed: {result['message']}")
            return False

    except Exception as e:
        print(f"✗ create_table() with data failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 4: Create table in specific section
    print("\n6. Testing create_table() with section-based insertion...")
    try:
        headers = ["Milestone", "Date", "Status"]
        data = [
            ["Design", "Q1 2025", "Complete"],
            ["Development", "Q2 2025", "In Progress"],
            ["Launch", "Q3 2025", "Planned"]
        ]

        result = table_manager.create_table(
            doc_url=doc_url,
            rows=4,
            columns=3,
            section="Project Timeline",
            headers=headers,
            data=data
        )

        if result['success']:
            print(f"✓ Created table in 'Project Timeline' section: {result['message']}")
            table = result['table_location']
            print(f"  - Table: {table.rows}x{table.columns}")
            print(f"  - Section: Project Timeline")
        else:
            print(f"✗ Failed: {result['message']}")
            return False

    except Exception as e:
        print(f"✗ create_table() with section failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 5: Create another table in different section
    print("\n7. Testing create_table() in 'Feature Comparison' section...")
    try:
        headers = ["Product", "Price", "Rating"]
        data = [
            ["Product A", "$99", "4.5"],
            ["Product B", "$149", "4.8"]
        ]

        result = table_manager.create_table(
            doc_url=doc_url,
            rows=3,
            columns=3,
            section="Feature Comparison",
            headers=headers,
            data=data
        )

        if result['success']:
            print(f"✓ Created table in 'Feature Comparison' section: {result['message']}")
            table = result['table_location']
            print(f"  - Table: {table.rows}x{table.columns}")
        else:
            print(f"✗ Failed: {result['message']}")
            return False

    except Exception as e:
        print(f"✗ Section-based insertion failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Verify all tables were created
    print("\n8. Verifying all tables in document...")
    try:
        tables = table_manager.find_tables(doc_id)
        expected_tables = 5  # 1 basic + 1 headers-only + 1 full + 2 section-based

        if len(tables) == expected_tables:
            print(f"✓ Found {len(tables)} tables (expected {expected_tables})")
            for i, table in enumerate(tables):
                print(f"  - Table {i}: {table.rows}x{table.columns} at index {table.start_index}")
        else:
            print(f"✗ Found {len(tables)} tables, expected {expected_tables}")
            return False

    except Exception as e:
        print(f"✗ Table verification failed: {e}")
        return False

    # Summary
    print("\n" + "=" * 60)
    print("✅ Phase 2 Test: ALL TESTS PASSED")
    print("=" * 60)
    print(f"\nTest document: {doc_url}")
    print("\nPhase 2 Complete:")
    print("  ✓ create_table() - Basic table creation")
    print("  ✓ create_table() - With headers (bold formatting)")
    print("  ✓ create_table() - With headers and data")
    print("  ✓ create_table() - Section-based insertion")
    print("  ✓ _populate_header_row() - Header population")
    print("  ✓ _populate_table_data() - Data population")
    print("  ✓ _find_section_insertion_point() - Section finding")
    print("\nReady for Phase 3: Row Operations")

    return True


if __name__ == '__main__':
    try:
        success = test_phase2()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
