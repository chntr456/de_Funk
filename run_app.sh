#!/bin/bash
#
# Run the Notebook Application (DuckDB-powered)
#
# This script starts the Streamlit-based notebook application with DuckDB backend.
# DuckDB provides 10-100x faster queries compared to Spark for interactive use.
#

echo "=================================================="
echo "  Starting Notebook Application (DuckDB)"
echo "=================================================="
echo ""

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "ERROR: Streamlit is not installed."
    echo ""
    echo "Please install it with:"
    echo "  pip install streamlit plotly pyyaml pandas duckdb pyarrow"
    echo ""
    echo "Note: pyspark is NOT required for this DuckDB-powered app!"
    echo ""
    exit 1
fi

# Check if running from repo root
if [ ! -d "configs/notebooks" ]; then
    echo "ERROR: Please run this script from the repository root directory."
    echo ""
    echo "Usage:"
    echo "  ./run_app.sh"
    echo ""
    exit 1
fi

echo "Starting Streamlit application..."
echo ""
echo "The app will open in your browser at: http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the server."
echo ""

# Run the Streamlit app
streamlit run app/ui/notebook_app_duckdb.py
