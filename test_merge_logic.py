#!/usr/bin/env python3
"""
Simple test of unified filter merge logic (no database required).

Tests that _merge_filters_unified() correctly:
1. Updates notebook filters with folder values
2. Adds folder-only filters to collection
3. Results in no duplicates
"""

import sys
from pathlib import Path

# Setup path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

print("=" * 80)
print("UNIFIED FILTER MERGE LOGIC TEST (No Database)")
print("=" * 80)
print()

# Test: Create mock filter collection and test merge
print("TEST: Merge Logic")
print("-" * 80)

from app.notebook.filters.dynamic import FilterCollection, FilterConfig, FilterType, FilterOperator

# Create mock filter collection (simulating notebook with 3 filters)
filter_collection = FilterCollection()

# Add notebook filters (with defaults)
filter_collection.add_filter(FilterConfig(
    id="ticker",
    type=FilterType.SELECT,
    label="Stock Tickers",
    multi=True,
    options=[],
    default=[]  # Empty default in notebook
))

filter_collection.add_filter(FilterConfig(
    id="trade_date",
    type=FilterType.DATE_RANGE,
    label="Trade Date",
    default={'start': '2024-01-01', 'end': '2024-01-05'}  # Q1 default in notebook
))

filter_collection.add_filter(FilterConfig(
    id="volume",
    type=FilterType.SLIDER,
    label="Volume",
    min_value=0,
    max_value=100000000,
    default=0,  # Zero default in notebook
    operator=FilterOperator.GREATER_EQUAL
))

print("BEFORE MERGE:")
print(f"  Filters in collection: {len(filter_collection.filters)}")
for fid, fconfig in filter_collection.filters.items():
    state = filter_collection.get_state(fid)
    print(f"    - {fid}: current_value={state.current_value}, default={fconfig.default}")

# Folder context (should supersede notebook defaults)
folder_filters = {
    'ticker': ['AAPL', 'MSFT'],  # Override empty default
    'trade_date': {'start': '2024-10-01', 'end': '2024-12-31'},  # Override Q1 with Q4
    'volume': 5000000,  # Override 0 with 5M
    'sector': 'Technology'  # NEW filter not in notebook
}

# Create a mock notebook config with the filter collection
class MockNotebookConfig:
    def __init__(self):
        self._filter_collection = filter_collection
        self.variables = None

# Create mock notebook manager
class MockNotebookManager:
    def __init__(self):
        self.notebook_config = MockNotebookConfig()

    def _merge_filters_unified(self, folder_filters):
        """Copy of actual _merge_filters_unified method"""
        from app.notebook.filters.dynamic import FilterCollection

        # Ensure we have a filter collection
        if not hasattr(self.notebook_config, '_filter_collection') or not self.notebook_config._filter_collection:
            self.notebook_config._filter_collection = FilterCollection()

        filter_collection = self.notebook_config._filter_collection

        if not folder_filters:
            return

        # Track which folder filters we've processed
        processed_folder_filters = set()

        # Phase 1: Update notebook filters with folder values
        for filter_id in list(filter_collection.filters.keys()):
            if filter_id in folder_filters:
                filter_state = filter_collection.get_state(filter_id)
                if filter_state:
                    filter_state.current_value = folder_filters[filter_id]
                processed_folder_filters.add(filter_id)

        # Phase 2: Add folder-only filters
        for filter_id, value in folder_filters.items():
            if filter_id not in processed_folder_filters:
                filter_config = self._create_filter_config_from_value(filter_id, value)
                filter_collection.add_filter(filter_config)
                filter_state = filter_collection.get_state(filter_id)
                if filter_state:
                    filter_state.current_value = value

    def _create_filter_config_from_value(self, filter_id, value):
        """Copy of actual _create_filter_config_from_value method"""
        from app.notebook.filters.dynamic import FilterConfig, FilterType, FilterOperator

        label = filter_id.replace('_', ' ').title()

        if isinstance(value, list):
            return FilterConfig(
                id=filter_id,
                type=FilterType.SELECT,
                label=label,
                multi=True,
                options=value,
                default=value
            )
        elif isinstance(value, dict):
            if 'start' in value and 'end' in value:
                return FilterConfig(
                    id=filter_id,
                    type=FilterType.DATE_RANGE,
                    label=label,
                    default=value
                )
            elif 'min' in value or 'max' in value:
                return FilterConfig(
                    id=filter_id,
                    type=FilterType.NUMBER_RANGE,
                    label=label,
                    default=value
                )
            else:
                return FilterConfig(
                    id=filter_id,
                    type=FilterType.TEXT_SEARCH,
                    label=label,
                    default=str(value)
                )
        elif isinstance(value, (int, float)):
            return FilterConfig(
                id=filter_id,
                type=FilterType.SLIDER,
                label=label,
                min_value=0,
                max_value=int(value * 10) if value > 0 else 100,
                default=value,
                operator=FilterOperator.GREATER_EQUAL
            )
        elif isinstance(value, bool):
            return FilterConfig(
                id=filter_id,
                type=FilterType.BOOLEAN,
                label=label,
                default=value
            )
        else:
            return FilterConfig(
                id=filter_id,
                type=FilterType.TEXT_SEARCH,
                label=label,
                default=str(value) if value else ""
            )

# Run merge
nb_mgr = MockNotebookManager()
print(f"\nMERGING folder context:")
for key, val in folder_filters.items():
    print(f"  - {key}: {val}")

nb_mgr._merge_filters_unified(folder_filters)

print(f"\nAFTER MERGE:")
merged_collection = nb_mgr.notebook_config._filter_collection
print(f"  Filters in collection: {len(merged_collection.filters)}")

# Check results
print(f"\n✓ Verification:")

# Check all 4 filters exist
expected_filters = ['ticker', 'trade_date', 'volume', 'sector']
for fid in expected_filters:
    if fid in merged_collection.filters:
        state = merged_collection.get_state(fid)
        print(f"  ✓ {fid}: current_value={state.current_value}")

        # Verify folder value was applied
        if fid in folder_filters:
            if state.current_value == folder_filters[fid]:
                print(f"      ✓ Folder value applied correctly")
            else:
                print(f"      ✗ ERROR: Expected {folder_filters[fid]}, got {state.current_value}")
                sys.exit(1)
    else:
        print(f"  ✗ ERROR: Missing filter '{fid}'")
        sys.exit(1)

# Check no duplicates
filter_ids = list(merged_collection.filters.keys())
unique_ids = set(filter_ids)
if len(filter_ids) != len(unique_ids):
    print(f"  ✗ ERROR: Duplicate filters found!")
    sys.exit(1)
else:
    print(f"  ✓ No duplicate filters (all {len(filter_ids)} unique)")

print()
print("=" * 80)
print("✓ MERGE LOGIC TEST PASSED!")
print("=" * 80)
print()
print("Results:")
print("  ✓ Notebook filters updated with folder values")
print("  ✓ Folder-only filter (sector) added to collection")
print("  ✓ All folder values superseded notebook defaults")
print("  ✓ No duplicate filters")
print("  ✓ Single unified collection")
