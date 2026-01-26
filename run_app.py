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

# Clear log file at startup for fresh debugging
repo_root = Path(__file__).parent
log_file = repo_root / "logs" / "de_funk.log"
if log_file.exists():
    log_file.write_text("")  # Clear the file

# Add src/ to path for de_funk package
sys.path.insert(0, str(repo_root / "src"))

# Initialize logging early
from de_funk.config.logging import setup_logging, get_logger

# Setup logging before anything else
setup_logging(repo_root=repo_root)
logger = get_logger(__name__)


def main():
    """Main entry point for the notebook application."""
    # User-facing banner (print is appropriate for CLI output)
    print("=" * 50)
    print("  Starting Notebook Application (DuckDB)")
    print("=" * 50)
    print()

    logger.info("Starting notebook application")

    # Check if running from repo root
    notebooks_dir = repo_root / "notebooks"

    if not notebooks_dir.exists():
        logger.error(f"Notebooks directory not found: {notebooks_dir}")
        print("ERROR: notebooks directory not found.")
        print()
        print("Please run this script from the repository root directory.")
        print()
        print("Usage:")
        print("  python run_app.py")
        print()
        sys.exit(1)

    # Path to the Streamlit app
    app_path = repo_root / "app" / "ui" / "notebook_app_duckdb.py"

    if not app_path.exists():
        logger.error(f"Application not found: {app_path}")
        print(f"ERROR: Application not found at {app_path}")
        sys.exit(1)

    # User-facing instructions
    print("Starting Streamlit application...")
    print()
    print("The app will open in your browser at: http://localhost:8501")
    print()
    print("Press Ctrl+C to stop the server.")
    print()

    logger.info(f"Launching Streamlit: {app_path}")

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
        logger.info("Application shutdown requested by user")
    except FileNotFoundError:
        logger.error("Streamlit not found - not installed")
        print()
        print("ERROR: Streamlit is not installed.")
        print()
        print("Please install required dependencies:")
        print("  pip install streamlit plotly pyyaml pandas duckdb pyarrow")
        print()
        print("Note: pyspark is NOT required for this DuckDB-powered app!")
        print()
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error running application: {e}")
        print(f"ERROR: Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
