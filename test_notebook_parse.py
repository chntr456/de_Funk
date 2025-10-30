#!/usr/bin/env python3
"""
Test script for notebook parsing with simplified format.

This script tests that:
1. Simplified notebook YAML parses correctly
2. Dimensions and measures are optional (None)
3. Exhibits have source field populated
"""

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("Notebook Parsing Test (Simplified Format)")
print("=" * 60)

try:
    # Import parser - use direct import to avoid __init__ issues
    print("\n1. Loading parser...")

    # Temporarily handle the import issue by mocking pyspark if needed
    try:
        from app.notebook.parser import NotebookParser
    except ModuleNotFoundError as e:
        if 'pyspark' in str(e):
            # Mock pyspark for parsing test
            import sys
            from unittest.mock import MagicMock
            sys.modules['pyspark'] = MagicMock()
            sys.modules['pyspark.sql'] = MagicMock()
            from app.notebook.parser import NotebookParser
        else:
            raise

    print("   ✓ Parser loaded")

    # Parse the simplified notebook
    print("\n2. Parsing simplified notebook YAML...")
    parser = NotebookParser(Path.cwd())
    config = parser.parse_file('configs/notebooks/stock_analysis.yaml')
    print("   ✓ Notebook parsed successfully")

    # Verify basic properties
    print("\n3. Verifying notebook properties...")
    print(f"   • Notebook ID: {config.notebook.id}")
    print(f"   • Title: {config.notebook.title}")
    print(f"   • Variables: {len(config.variables)}")
    print(f"   • Exhibits: {len(config.exhibits)}")

    # Check dimensions and measures are None/empty (simplified format)
    print("\n4. Checking simplified format...")
    if config.dimensions is None:
        print("   ✓ Dimensions: None (as expected in simplified format)")
    elif len(config.dimensions) == 0:
        print("   ✓ Dimensions: Empty list (as expected)")
    else:
        print(f"   ✗ ERROR: Dimensions should be None, got {len(config.dimensions)}")
        sys.exit(1)

    if config.measures is None:
        print("   ✓ Measures: None (as expected in simplified format)")
    elif len(config.measures) == 0:
        print("   ✓ Measures: Empty list (as expected)")
    else:
        print(f"   ✗ ERROR: Measures should be None, got {len(config.measures)}")
        sys.exit(1)

    # Check exhibits have source field
    print("\n5. Verifying exhibit sources...")
    all_have_source = True
    for exhibit in config.exhibits:
        if exhibit.source:
            print(f"   ✓ {exhibit.id}: {exhibit.source}")
        else:
            print(f"   ✗ {exhibit.id}: No source!")
            all_have_source = False

    if not all_have_source:
        print("\n   ✗ ERROR: Some exhibits missing source field")
        sys.exit(1)

    # Verify specific exhibit properties
    print("\n6. Verifying exhibit details...")

    # Check price_overview exhibit
    price_overview = next((e for e in config.exhibits if e.id == 'price_overview'), None)
    if price_overview:
        print(f"   • price_overview:")
        print(f"     - source: {price_overview.source}")
        print(f"     - metrics: {len(price_overview.metrics)}")
        if price_overview.metrics:
            measures = [m.measure for m in price_overview.metrics]
            print(f"     - measure IDs: {measures}")

    # Check price_trend exhibit
    price_trend = next((e for e in config.exhibits if e.id == 'price_trend'), None)
    if price_trend:
        print(f"   • price_trend:")
        print(f"     - source: {price_trend.source}")
        print(f"     - x_axis dimension: {price_trend.x_axis.dimension if price_trend.x_axis else None}")
        if price_trend.y_axis and price_trend.y_axis.measures:
            print(f"     - y_axis measures: {price_trend.y_axis.measures}")

    # Check detailed_prices exhibit
    detailed_prices = next((e for e in config.exhibits if e.id == 'detailed_prices'), None)
    if detailed_prices:
        print(f"   • detailed_prices:")
        print(f"     - source: {detailed_prices.source}")
        print(f"     - columns: {detailed_prices.columns}")

    # Success summary
    print("\n" + "=" * 60)
    print("✓ SUCCESS: Simplified notebook format works correctly!")
    print("=" * 60)
    print("\nKey improvements:")
    print("  • No dimension definitions in YAML (uses model)")
    print("  • No measure definitions in YAML (uses model)")
    print("  • Exhibits reference model.table directly")
    print("  • Cleaner, more maintainable format")
    print()

except ImportError as e:
    print(f"\n✗ ERROR: Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
