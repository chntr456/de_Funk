#!/usr/bin/env python3
"""
UI State Tester - Shows what should appear in Streamlit UI

This simulates what the filter widgets should display based on
folder context and notebook configuration.

Usage:
    python test_ui_state.py
"""

import sys
from pathlib import Path

repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

print("=" * 80)
print("UI STATE TEST - What Should Appear in Streamlit")
print("=" * 80)
print()

# Initialize
from core.context import RepoContext
from app.session.universal_session import UniversalSession
from app.notebook.managers.notebook_manager import NotebookManager

ctx = RepoContext.from_repo_root(connection_type="duckdb")
session = UniversalSession(
    connection=ctx.connection,
    storage_cfg=ctx.storage,
    repo_root=ctx.repo
)

notebooks_root = ctx.repo / "configs" / "notebooks"
nb_manager = NotebookManager(session, ctx.repo, notebooks_root)

# Test notebook
test_notebook = notebooks_root / "Financial Analysis" / "stock_analysis.md"
if not test_notebook.exists():
    test_notebook = notebooks_root / "stock_analysis.md"

print(f"Loading: {test_notebook.relative_to(ctx.repo)}")
print()

# Load notebook
try:
    nb_config = nb_manager.load_notebook(str(test_notebook))

    print("EXPECTED STREAMLIT UI:")
    print("=" * 80)
    print()

    # Sidebar section 1: Folder Filter Editor
    print("📁 FOLDER FILTER EDITOR SECTION")
    print("-" * 80)

    current_folder = nb_manager.get_current_folder()
    folder_name = current_folder.name if current_folder else "Unknown"

    print(f"### 📁 Folder: {folder_name}")
    print("_Filters shared by all notebooks in this folder_")
    print()

    # Show what .filter_context.yaml contains
    folder_filters = nb_manager.folder_context_manager.get_filters(current_folder)

    if folder_filters:
        print("📊 Active Filters (from .filter_context.yaml):")
        for key, value in folder_filters.items():
            if isinstance(value, list):
                print(f"  • {key}: {', '.join(map(str, value))}")
            elif isinstance(value, dict):
                print(f"  • {key}: {value}")
            else:
                print(f"  • {key}: {value}")
    else:
        print("📝 No filters set")

    print()
    print("[✏️ Edit Filter Context] button")
    print()

    # Sidebar section 2: Filter Widgets
    print("🎛️ FILTER WIDGETS SECTION")
    print("-" * 80)
    print()

    # Check for extra folder filters (not in notebook)
    extra_filters = getattr(nb_manager, '_extra_folder_filters', {})

    if extra_filters:
        print("📁 **Folder Filters** (applied automatically)")
        print()
        for var_id, value in extra_filters.items():
            # Skip if in notebook variables
            if nb_config.variables and var_id in nb_config.variables:
                continue

            # Show what widget would be rendered
            label = var_id.replace('_', ' ').title()

            if isinstance(value, list):
                print(f"  [{label}] Multiselect")
                print(f"    Options: {value}")
                print(f"    Default: {value}")
            elif isinstance(value, dict) and 'start' in value:
                print(f"  [{label} (Start)] Date Input")
                print(f"    Default: {value['start']}")
                print(f"  [{label} (End)] Date Input")
                print(f"    Default: {value['end']}")
            elif isinstance(value, dict) and 'min' in value:
                print(f"  [{label}] Number Range Slider")
                print(f"    Range: {value.get('min', 0)} - {value.get('max', 1000000)}")
            elif isinstance(value, (int, float)):
                print(f"  [{label}] Number Input")
                print(f"    Default: {value}")
            else:
                print(f"  [{label}] Text Input")
                print(f"    Default: {value}")
            print()

        print("─" * 40)
        print()

    # Show notebook-defined filters
    if nb_config.variables:
        print("📋 **Notebook Filters**")
        print()

        filter_context = nb_manager.get_filter_context()

        for var_id, variable in nb_config.variables.items():
            current_value = filter_context.get(var_id)

            print(f"  [{variable.display_name}] {variable.type.value}")
            if current_value is not None:
                print(f"    Current Value: {current_value}")
            else:
                print(f"    Current Value: (default)")
            print()
    else:
        print("ℹ Notebook defines no filter variables")
        print()

    print()

    # Main content section: Exhibits
    print("📊 MAIN CONTENT - EXHIBITS")
    print("-" * 80)
    print()

    # Show what filters would be applied to exhibits
    if nb_config.exhibits:
        print(f"Rendering {len(nb_config.exhibits)} exhibits")
        print()

        for exhibit in nb_config.exhibits[:3]:  # Show first 3
            print(f"  Exhibit: {exhibit.id}")

            # Build filters for this exhibit
            filters = nb_manager._build_filters(exhibit)

            if filters:
                print(f"  Filters applied to query:")
                for key, value in filters.items():
                    print(f"    - {key}: {value}")
            else:
                print(f"  (no filters applied)")

            print()
    else:
        print("No exhibits defined")
        print()

    print()

    # Summary
    print("VERIFICATION CHECKLIST")
    print("=" * 80)
    print()

    # Check 1: Folder context loaded
    if folder_filters:
        print("✓ Folder filters loaded from .filter_context.yaml")
    else:
        print("✗ No folder filters loaded")

    # Check 2: Extra filters stored
    if extra_filters:
        print(f"✓ {len(extra_filters)} extra folder filters stored")
        for key in extra_filters.keys():
            print(f"    - {key}")
    else:
        print("ℹ No extra folder filters (all match notebook variables)")

    # Check 3: Filters will be applied
    test_exhibit = nb_config.exhibits[0] if nb_config.exhibits else None
    if test_exhibit:
        test_filters = nb_manager._build_filters(test_exhibit)
        if test_filters:
            print(f"✓ {len(test_filters)} filters will be applied to exhibits")
            for key in test_filters.keys():
                print(f"    - {key}")
        else:
            print("✗ NO filters will be applied to exhibits")

    print()

    # Expected behavior
    print("EXPECTED BEHAVIOR:")
    print("-" * 80)
    print()
    print("When you open this notebook in Streamlit, you should see:")
    print()
    print("1. FOLDER FILTER EDITOR shows the folder name and active filters")
    print("2. FILTER WIDGETS section shows:")

    if extra_filters:
        print("   - '📁 Folder Filters (applied automatically)' section")
        print("   - Auto-generated widgets for each extra folder filter")

    if nb_config.variables:
        print("   - '📋 Notebook Filters' section")
        print("   - Widgets for each notebook-defined variable")

    print("3. EXHIBITS are filtered using ALL folder + notebook filters")
    print("4. Data in exhibits matches the filter values")
    print()

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("=" * 80)
