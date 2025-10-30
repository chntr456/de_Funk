# Running the Notebook Application

This guide explains how to run the refactored notebook application.

## Prerequisites

### Required Dependencies

Install the required Python packages:

```bash
pip install streamlit plotly pyyaml pyspark pandas
```

Or install all dependencies at once:

```bash
pip install -r requirements.txt
```

### Required Data

The application expects data in the Silver layer. If you haven't built it yet:

```bash
python test_build_silver.py
```

This will:
1. Load Bronze data from `storage/bronze/`
2. Build Silver layer tables (dimensions and facts)
3. Write to `storage/silver/company/`

## Running the Application

### Option 1: Using the Shell Script (Linux/Mac)

```bash
./run_app.sh
```

### Option 2: Using the Python Script (All Platforms)

```bash
python run_app.py
```

### Option 3: Direct Streamlit Command

```bash
streamlit run src/ui/notebook_app_professional.py
```

## What to Expect

1. **Server Starts**: Streamlit server starts on http://localhost:8501
2. **Browser Opens**: Your default browser should open automatically
3. **Application Loads**: The notebook application interface appears

## Application Features

### 1. **Sidebar Navigation** 📚
- Browse available notebooks in `configs/notebooks/`
- Organized by directory
- Click to open notebooks in tabs

### 2. **Filters Section** 🎛️
- Dynamic filters based on notebook variables
- Date range picker
- Multi-select for tickers
- Number inputs for thresholds

### 3. **Main Content Area**
- **View Mode**: Rendered exhibits (charts, tables, metrics)
- **Edit Mode**: YAML editor with syntax validation
- Toggle between modes with the button

### 4. **Exhibit Types**
- **Metric Cards**: Key performance indicators
- **Line Charts**: Time series trends
- **Bar Charts**: Categorical comparisons
- **Data Tables**: Detailed tabular data with download

### 5. **Theme Toggle** 🌓
- Light mode (professional light theme)
- Dark mode (professional dark theme)
- Toggle in sidebar

## Current Notebooks

### Stock Analysis (`configs/notebooks/stock_analysis.yaml`)

Analyzes stock performance with:
- Price overview metrics
- Daily price trends
- Volume comparisons
- Detailed price data

**Exhibits:**
- Price Overview (metric cards)
- Daily Closing Prices (line chart)
- Trading Volume by Stock (bar chart)
- Detailed Price Data (data table)

## Architecture Overview

The refactored application uses a modular component architecture:

```
src/ui/
├── components/
│   ├── theme.py              # Professional theme styling
│   ├── sidebar.py            # Navigation and tab management
│   ├── filters.py            # Filter controls
│   ├── yaml_editor.py        # YAML editing
│   ├── notebook_view.py      # Exhibit orchestration
│   └── exhibits/
│       ├── metric_cards.py   # Metric card rendering
│       ├── line_chart.py     # Line chart rendering
│       ├── bar_chart.py      # Bar chart rendering
│       └── data_table.py     # Data table rendering
└── notebook_app_professional.py  # Main application
```

## Configuration

### Model Configuration (`configs/models/company.yaml`)

Defines:
- Storage paths and format
- Schema (dimensions and facts)
- Pre-defined measures
- Graph structure

### Notebook Configuration (`configs/notebooks/*.yaml`)

Simplified format (model-centric):
- No dimension definitions (uses model)
- No measure definitions (uses model)
- Exhibits reference `model.table` directly
- Variables for filtering
- Layout sections

## Troubleshooting

### "No module named 'streamlit'"

Install Streamlit:
```bash
pip install streamlit
```

### "No module named 'pyspark'"

Install PySpark:
```bash
pip install pyspark
```

### "Silver layer not found"

Build the Silver layer:
```bash
python test_build_silver.py
```

### "No notebooks found"

Ensure you have YAML files in `configs/notebooks/`:
```bash
ls configs/notebooks/
```

### Port Already in Use

If port 8501 is already in use, specify a different port:
```bash
streamlit run src/ui/notebook_app_professional.py --server.port=8502
```

## Development

### Adding New Notebooks

1. Create a YAML file in `configs/notebooks/`
2. Reference model and tables using `source: model.table`
3. Define variables for filtering
4. Define exhibits for visualization
5. Define layout sections

### Adding New Exhibit Types

1. Create a new module in `src/ui/components/exhibits/`
2. Implement the `render_*` function
3. Add to `src/ui/components/exhibits/__init__.py`
4. Update `src/ui/components/notebook_view.py` to handle the new type

### Adding New Models

1. Create a YAML file in `configs/models/`
2. Define storage configuration
3. Define schema (dimensions and facts)
4. Define measures
5. Build the model data

## Next Steps

The current application (`notebook_app_professional.py`) will be migrated to use:
- New modular components from `src/ui/components/`
- `NotebookService` instead of `NotebookSession`
- Generic `StorageService`

For now, it continues to work with the existing architecture while the new components are integrated.

## Support

For issues or questions:
1. Check the error message in the terminal
2. Review the logs in the Streamlit app
3. Verify your data exists in `storage/silver/`
4. Ensure all dependencies are installed
