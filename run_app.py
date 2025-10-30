#!/usr/bin/env python3
"""
Run the Notebook Application (DuckDB-powered)

This script starts the Streamlit-based notebook application with DuckDB backend.
DuckDB provides 10-100x faster queries compared to Spark for interactive use.

Benefits:
- Instant startup (~1s vs ~15s with Spark)
- 10-100x faster queries
- No JVM overhead
- No pyspark required!
"""

import sys
import subprocess
from pathlib import Path

def main():
    print("=" * 50)
    print("  Starting Notebook Application (DuckDB)")
    print("=" * 50)
    print()

    # Check if running from repo root
    repo_root = Path(__file__).parent
    notebooks_dir = repo_root / "configs" / "notebooks"

    if not notebooks_dir.exists():
        print("ERROR: configs/notebooks directory not found.")
        print()
        print("Please run this script from the repository root directory.")
        print()
        print("Usage:")
        print("  python run_app.py")
        print()
        sys.exit(1)

    # Path to the Streamlit app
    app_path = repo_root / "src" / "ui" / "notebook_app_professional.py"

    if not app_path.exists():
        print(f"ERROR: Application not found at {app_path}")
        sys.exit(1)

    print("Starting Streamlit application...")
    print()
    print("The app will open in your browser at: http://localhost:8501")
    print()
    print("Press Ctrl+C to stop the server.")
    print()

    try:
        # Run streamlit
        subprocess.run([
            "streamlit", "run", str(app_path),
            "--server.port=8501",
            "--server.headless=false",
        ])
    except KeyboardInterrupt:
        print()
        print("Shutting down...")
    except FileNotFoundError:
        print()
        print("ERROR: Streamlit is not installed.")
        print()
        print("Please install required dependencies:")
        print("  pip install streamlit plotly pyyaml pandas duckdb pyarrow")
        print()
        print("Note: pyspark is NOT required for this DuckDB-powered app!")
        print()
        sys.exit(1)

if __name__ == "__main__":
    main()
