#!/usr/bin/env python3
"""
Test Notebook Rendering Pipeline

This script traces through the actual notebook rendering pipeline to find
where the "[object Object]" error occurs.

Usage:
    python -m scripts.test.test_notebook_rendering
"""

import sys
from pathlib import Path
from utils.repo import setup_repo_imports

repo_root = setup_repo_imports()

def test_notebook_rendering():
    """Test the full notebook rendering pipeline."""

    print("=" * 80)
    print("NOTEBOOK RENDERING PIPELINE TEST")
    print("=" * 80)

    # Step 1: Load the notebook configuration
    print("\n[1] Loading notebook configuration...")
    print("-" * 80)

    try:
        from app.notebook.parsers.markdown_parser import parse_markdown_notebook

        notebook_path = repo_root / "configs" / "notebooks" / "stocks" / "stock_analysis_v2.md"

        if not notebook_path.exists():
            print(f"❌ Notebook not found: {notebook_path}")
            print("\nAvailable notebooks:")
            notebooks_dir = repo_root / "configs" / "notebooks"
            for nb_file in notebooks_dir.rglob("*.md"):
                print(f"  - {nb_file.relative_to(notebooks_dir)}")
            return

        with open(notebook_path) as f:
            content = f.read()

        notebook_config = parse_markdown_notebook(content, notebook_path.stem)
        print(f"✓ Loaded notebook: {notebook_config.notebook.title}")
        print(f"  Exhibits: {len(notebook_config.exhibits)}")

    except Exception as e:
        print(f"❌ Failed to load notebook: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 2: Create notebook session
    print("\n[2] Creating notebook session...")
    print("-" * 80)

    try:
        from app.notebook.api.notebook_session import NotebookSession
        from core.duckdb_connection import DuckDBConnection
        from app.services.storage_service import SilverStorageService
        from models.registry import ModelRegistry
        import json

        # Load configs
        with open(repo_root / "configs" / "storage.json") as f:
            storage_cfg = json.load(f)

        # Create connection
        conn = DuckDBConnection()

        # Create model registry
        registry = ModelRegistry(repo_root / "configs" / "models")

        # Create storage service
        storage_service = SilverStorageService(conn, registry)

        # Create notebook session
        notebook_session = NotebookSession(
            notebook_config=notebook_config,
            storage_service=storage_service,
            connection=conn
        )

        print(f"✓ Notebook session created")

    except Exception as e:
        print(f"❌ Failed to create session: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 3: Test getting exhibit data
    print("\n[3] Testing exhibit data retrieval...")
    print("-" * 80)

    if len(notebook_config.exhibits) == 0:
        print("⚠️ No exhibits found in notebook")
        return

    # Get first exhibit
    first_exhibit = notebook_config.exhibits[0]
    print(f"Testing exhibit: {first_exhibit.id}")
    print(f"  Title: {first_exhibit.title}")
    print(f"  Type: {first_exhibit.type}")

    try:
        # Get exhibit data (this is what the UI does)
        df = notebook_session.get_exhibit_data(first_exhibit.id)

        print(f"✓ Got exhibit data")
        print(f"  Type: {type(df)}")
        print(f"  Has .data attribute: {hasattr(df, 'data')}")

        # Step 4: Test conversion to pandas
        print("\n[4] Testing conversion to pandas...")
        print("-" * 80)

        pdf = conn.to_pandas(df)

        print(f"✓ Converted to pandas")
        print(f"  Type after conversion: {type(pdf)}")
        print(f"  Shape: {pdf.shape}")
        print(f"  Columns: {list(pdf.columns)}")
        print(f"  Dtypes:")
        for col in pdf.columns:
            print(f"    {col:20s} {str(pdf[col].dtype):15s}")

        # Step 5: Test JSON serialization (what Streamlit does)
        print("\n[5] Testing JSON serialization...")
        print("-" * 80)

        try:
            json_str = pdf.to_json(orient='records', date_format='iso')
            print(f"✓ JSON serialization successful")
            print(f"  JSON length: {len(json_str)} characters")

            import json
            data = json.loads(json_str)
            print(f"  First record: {data[0] if data else 'N/A'}")

        except Exception as e:
            print(f"❌ JSON serialization failed: {e}")

            # Find problematic columns
            print("\nTesting individual columns...")
            for col in pdf.columns:
                try:
                    test_df = pdf[[col]]
                    test_json = test_df.to_json(orient='records')
                    print(f"  ✓ {col}")
                except Exception as col_e:
                    print(f"  ❌ {col}: {col_e}")

        # Step 6: Test Streamlit dataframe display
        print("\n[6] Testing Streamlit display simulation...")
        print("-" * 80)

        try:
            # Check if any columns have objects that can't be serialized
            problematic = []
            for col in pdf.columns:
                if pdf[col].dtype == 'object':
                    # Check first non-null value
                    sample_values = pdf[col].dropna()
                    if len(sample_values) > 0:
                        sample = sample_values.iloc[0]
                        if not isinstance(sample, (str, int, float, bool, type(None))):
                            problematic.append((col, type(sample).__name__))

            if problematic:
                print("⚠️ Found columns with non-primitive types:")
                for col, dtype in problematic:
                    print(f"  - {col}: {dtype}")
                    # Show sample value
                    sample = pdf[col].dropna().iloc[0] if len(pdf[col].dropna()) > 0 else None
                    print(f"    Sample: {repr(sample)}")
            else:
                print("✓ All columns have primitive types")

        except Exception as e:
            print(f"❌ Type check failed: {e}")

        # Step 7: Display sample data
        print("\n[7] Sample data (first 5 rows):")
        print("-" * 80)
        print(pdf.head().to_string(index=False))

    except Exception as e:
        print(f"❌ Failed to get exhibit data: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 80)
    print("✓ Pipeline test complete")
    print("=" * 80)

    conn.stop()


if __name__ == "__main__":
    test_notebook_rendering()
