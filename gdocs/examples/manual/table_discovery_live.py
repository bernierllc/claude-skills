#!/usr/bin/env python3
"""
Test Phase 1: Table Discovery

Tests all Phase 1 table discovery functionality:
- find_tables() - Find all tables in document
- get_table_at_index() - Get specific table
- find_cell_location() - Find cell indices
- _build_table_cell_location() - Build API-compatible location dict
"""

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.table_manager import TableManager


def test_phase1():
    """Test Phase 1 table discovery functionality."""
    print("=" * 60)
    print("Phase 1 Table Discovery Test")
    print("=" * 60)

    # Initialize
    editor = GoogleDocsEditor()
    table_manager = TableManager(editor)

    # Create test document with table
    print("\n1. Creating test document with table...")
    doc_result = editor.create_document("Table Manager Test - Phase 1")
    doc_id = doc_result['doc_id']
    doc_url = doc_result['doc_url']

    print(f"✓ Created document: {doc_url}")

    # Create a simple table using Google Docs API
    print("\n2. Creating test table (3x3)...")
    try:
        # Insert table at beginning of document
        requests = [{
            'insertTable': {
                'rows': 3,
                'columns': 3,
                'location': {
                    'index': 1  # After document start
                }
            }
        }]

        editor.docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()

        print("✓ Created 3x3 table")

    except Exception as e:
        print(f"✗ Failed to create table: {e}")
        return False

    # Test find_tables()
    print("\n3. Testing find_tables()...")
    try:
        tables = table_manager.find_tables(doc_id)
        print(f"✓ Found {len(tables)} table(s)")

        if len(tables) > 0:
            table = tables[0]
            print(f"  - Table 0: {table.rows}x{table.columns} at indices {table.start_index}-{table.end_index}")
        else:
            print("✗ No tables found (expected 1)")
            return False

    except Exception as e:
        print(f"✗ find_tables() failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test get_table_at_index()
    print("\n4. Testing get_table_at_index()...")
    try:
        table = table_manager.get_table_at_index(doc_id, 0)
        if table:
            print(f"✓ Retrieved table 0: {table.rows}x{table.columns}")
        else:
            print("✗ get_table_at_index(0) returned None")
            return False

        # Test invalid index
        table = table_manager.get_table_at_index(doc_id, 5)
        if table is None:
            print("✓ get_table_at_index(5) correctly returned None")
        else:
            print("✗ get_table_at_index(5) should return None")
            return False

    except Exception as e:
        print(f"✗ get_table_at_index() failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test find_cell_location()
    print("\n5. Testing find_cell_location()...")
    try:
        # Find cell at row 0, column 0
        cell = table_manager.find_cell_location(doc_id, table_index=0, row=0, column=0)
        if cell:
            print(f"✓ Found cell (0,0): indices {cell.cell_start_index}-{cell.cell_end_index}")
        else:
            print("✗ find_cell_location(0,0) returned None")
            return False

        # Find cell at row 1, column 2
        cell = table_manager.find_cell_location(doc_id, table_index=0, row=1, column=2)
        if cell:
            print(f"✓ Found cell (1,2): indices {cell.cell_start_index}-{cell.cell_end_index}")
        else:
            print("✗ find_cell_location(1,2) returned None")
            return False

        # Test invalid cell
        cell = table_manager.find_cell_location(doc_id, table_index=0, row=10, column=0)
        if cell is None:
            print("✓ find_cell_location(10,0) correctly returned None")
        else:
            print("✗ find_cell_location(10,0) should return None")
            return False

    except Exception as e:
        print(f"✗ find_cell_location() failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test _build_table_cell_location()
    print("\n6. Testing _build_table_cell_location()...")
    try:
        loc = table_manager._build_table_cell_location(100, 1, 2)
        expected_keys = {'tableStartLocation', 'rowIndex', 'columnIndex'}
        if set(loc.keys()) == expected_keys:
            print("✓ Built correct tableCellLocation structure")
            print(f"  - tableStartLocation: {loc['tableStartLocation']}")
            print(f"  - rowIndex: {loc['rowIndex']}")
            print(f"  - columnIndex: {loc['columnIndex']}")
        else:
            print(f"✗ Incorrect structure. Expected keys: {expected_keys}, got: {set(loc.keys())}")
            return False

    except Exception as e:
        print(f"✗ _build_table_cell_location() failed: {e}")
        return False

    # Summary
    print("\n" + "=" * 60)
    print("✅ Phase 1 Test: ALL TESTS PASSED")
    print("=" * 60)
    print(f"\nTest document: {doc_url}")
    print("\nPhase 1 Complete:")
    print("  ✓ find_tables() - Discovers all tables in document")
    print("  ✓ get_table_at_index() - Retrieves specific table")
    print("  ✓ find_cell_location() - Calculates cell indices")
    print("  ✓ _build_table_cell_location() - Builds API-compatible dict")
    print("\nReady for Phase 2: Table Creation")

    return True


if __name__ == '__main__':
    try:
        success = test_phase1()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
