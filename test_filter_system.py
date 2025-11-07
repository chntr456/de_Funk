#!/usr/bin/env python3
"""
Comprehensive Filter System Test

Run this to verify:
1. Folder context loading
2. Filter application to queries
3. Dynamic widget generation
4. End-to-end filter flow

Usage:
    python test_filter_system.py
"""

import sys
from pathlib import Path
from datetime import datetime

# Add repo to path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

print("=" * 80)
print("FILTER SYSTEM COMPREHENSIVE TEST")
print("=" * 80)
print()

# Test 1: Check folder context files exist
print("TEST 1: Folder Context Files")
print("-" * 80)

notebooks_root = repo_root / "configs" / "notebooks"
test_files = {
    "Financial Analysis": notebooks_root / "Financial Analysis" / ".filter_context.yaml",
    "Root": notebooks_root / ".filter_context.yaml"
}

for name, path in test_files.items():
    if path.exists():
        print(f"✓ {name}: {path.relative_to(repo_root)}")
        with open(path) as f:
            content = f.read()
            print(f"  Content preview: {content[:200]}...")
    else:
        print(f"✗ {name}: NOT FOUND at {path.relative_to(repo_root)}")

print()

# Test 2: Load folder context manager
print("TEST 2: Folder Context Manager Loading")
print("-" * 80)

try:
    from app.notebook.folder_context import FolderFilterContextManager

    manager = FolderFilterContextManager(notebooks_root)
    print("✓ FolderFilterContextManager initialized")

    # Test Financial Analysis folder
    fa_folder = notebooks_root / "Financial Analysis"
    fa_filters = manager.get_filters(fa_folder)
    print(f"\n✓ Financial Analysis folder filters loaded:")
    for key, value in fa_filters.items():
        print(f"  - {key}: {value}")

    # Test root folder
    root_filters = manager.get_filters(notebooks_root)
    print(f"\n✓ Root folder filters loaded:")
    for key, value in root_filters.items():
        print(f"  - {key}: {value}")

except Exception as e:
    print(f"✗ Error loading folder context: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 3: Initialize NotebookManager
print("TEST 3: NotebookManager Initialization")
print("-" * 80)

try:
    from core.context import RepoContext
    from app.session.universal_session import UniversalSession
    from app.notebook.managers.notebook_manager import NotebookManager

    # Initialize context
    ctx = RepoContext.from_repo_root(connection_type="duckdb")
    print("✓ RepoContext initialized")

    # Initialize session
    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )
    print("✓ UniversalSession initialized")

    # Initialize notebook manager
    nb_manager = NotebookManager(session, ctx.repo, notebooks_root)
    print("✓ NotebookManager initialized")

except Exception as e:
    print(f"✗ Error initializing managers: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 4: Load notebook and check filter context
print("TEST 4: Notebook Loading & Filter Context")
print("-" * 80)

test_notebook = notebooks_root / "Financial Analysis" / "stock_analysis.md"
if not test_notebook.exists():
    test_notebook = notebooks_root / "stock_analysis.md"

if test_notebook.exists():
    print(f"Loading: {test_notebook.relative_to(repo_root)}")

    try:
        nb_config = nb_manager.load_notebook(str(test_notebook))
        print(f"✓ Notebook loaded: {nb_config.title if hasattr(nb_config, 'title') else 'untitled'}")

        # Check current folder
        current_folder = nb_manager.get_current_folder()
        print(f"✓ Current folder: {current_folder.relative_to(notebooks_root) if current_folder else 'None'}")

        # Check filter context
        filter_context = nb_manager.get_filter_context()
        print(f"\n✓ FilterContext loaded with {len(filter_context)} filters:")
        for key, value in filter_context.items():
            print(f"  - {key}: {value}")

        # Check extra folder filters
        if hasattr(nb_manager, '_extra_folder_filters'):
            print(f"\n✓ Extra folder filters (not in notebook variables):")
            for key, value in nb_manager._extra_folder_filters.items():
                print(f"  - {key}: {value}")
        else:
            print(f"\nℹ No extra folder filters")

        # Check notebook variables
        if nb_config.variables:
            print(f"\n✓ Notebook defines {len(nb_config.variables)} variables:")
            for key, var in nb_config.variables.items():
                print(f"  - {key}: {var.type.value}")
        else:
            print(f"\nℹ Notebook defines NO variables")

    except Exception as e:
        print(f"✗ Error loading notebook: {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"✗ Test notebook not found: {test_notebook}")

print()

# Test 5: Test filter building
print("TEST 5: Filter Building (_build_filters)")
print("-" * 80)

if test_notebook.exists() and nb_config:
    try:
        # Create a mock exhibit
        from app.notebook.schema import Exhibit, ExhibitType

        mock_exhibit = Exhibit(
            id="test_exhibit",
            type=ExhibitType.METRIC_CARDS,
            source="company.fact_prices",
            metrics=[]
        )

        # Build filters
        filters = nb_manager._build_filters(mock_exhibit)

        print(f"✓ Filters built for exhibit:")
        if filters:
            for key, value in filters.items():
                print(f"  - {key}: {value}")
        else:
            print(f"  (no filters)")

        # Test what happens to a filter not in notebook variables
        print(f"\nℹ Testing filter application:")

        # Check if 'ticker' filter would be applied
        if 'ticker' in filters:
            print(f"  ✓ 'ticker' filter WILL BE APPLIED: {filters['ticker']}")
        else:
            print(f"  ✗ 'ticker' filter WILL NOT BE APPLIED (missing from filters dict)")

        # Check if 'volume' filter would be applied
        if 'volume' in filters:
            print(f"  ✓ 'volume' filter WILL BE APPLIED: {filters['volume']}")
        else:
            print(f"  ✗ 'volume' filter WILL NOT BE APPLIED (missing from filters dict)")

    except Exception as e:
        print(f"✗ Error building filters: {e}")
        import traceback
        traceback.print_exc()

print()

# Test 6: Test FilterEngine application
print("TEST 6: FilterEngine Application")
print("-" * 80)

try:
    from core.session.filters import FilterEngine

    # Test filter dict
    test_filters = {
        'ticker': ['AAPL', 'MSFT'],
        'volume': {'min': 5000000}
    }

    print(f"Test filters: {test_filters}")

    # Try to get a table and apply filters
    try:
        df = session.get_table('company', 'fact_prices')
        print(f"✓ Got raw data from company.fact_prices")

        # Apply filters
        filtered_df = FilterEngine.apply_from_session(df, test_filters, session)
        print(f"✓ FilterEngine.apply_from_session() executed")

        # Convert to pandas to check
        pdf = ctx.connection.to_pandas(filtered_df)
        print(f"✓ Converted to pandas: {len(pdf)} rows")

        if 'ticker' in pdf.columns:
            unique_tickers = pdf['ticker'].unique().tolist()
            print(f"  Unique tickers in result: {unique_tickers}")

            if set(unique_tickers) <= {'AAPL', 'MSFT'}:
                print(f"  ✓ Ticker filter WORKING (only AAPL/MSFT)")
            else:
                print(f"  ✗ Ticker filter NOT WORKING (found other tickers)")

        if 'volume' in pdf.columns:
            min_volume = pdf['volume'].min()
            print(f"  Minimum volume in result: {min_volume}")

            if min_volume >= 5000000:
                print(f"  ✓ Volume filter WORKING (all >= 5M)")
            else:
                print(f"  ✗ Volume filter NOT WORKING (found < 5M)")

    except Exception as e:
        print(f"✗ Error applying filters: {e}")
        import traceback
        traceback.print_exc()

except Exception as e:
    print(f"✗ Error testing FilterEngine: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 7: Summary
print("TEST 7: Summary")
print("=" * 80)

print("""
Key Questions to Answer:

1. Are .filter_context.yaml files being created and loaded?
2. Do folder filters load into FilterContext?
3. Are extra folder filters (not in notebook) stored in _extra_folder_filters?
4. Does _build_filters() include ALL folder filters in the output dict?
5. Does FilterEngine actually apply those filters to the data?
6. Do the filtered results match the folder filter values?

Review the output above to see which steps are working and which are failing.
""")

print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
