# Quick Start Guide

Get the notebook application running in 3 steps!

## Step 1: Install Dependencies

```bash
pip install streamlit plotly pyyaml pyspark pandas
```

## Step 2: Build Silver Layer Data (if needed)

```bash
python test_build_silver.py
```

This creates the processed data in `storage/silver/company/`.

**Expected output:**
- ✓ dim_company table created
- ✓ dim_exchange table created
- ✓ fact_prices table created
- ✓ prices_with_company view created

## Step 3: Run the Application

### Quick Run (Recommended)

```bash
./run_app.sh
```

Or on Windows/if shell script doesn't work:

```bash
python run_app.py
```

### Direct Streamlit Command

```bash
streamlit run app/ui/notebook_app_duckdb.py
```

## What You'll See

1. **Server starts** at http://localhost:8501
2. **Browser opens** automatically
3. **Sidebar shows** available notebooks
4. **Click** "stock_analysis" to open it
5. **View** charts, metrics, and tables

## Using the Application

### Open a Notebook
1. Look in the left sidebar under "📚 Notebooks"
2. Click on "stock_analysis"
3. The notebook opens in the main area

### Apply Filters
1. In the sidebar under "🎛️ Filters"
2. Adjust date range
3. Select stock tickers
4. Results update automatically

### Toggle Edit/View Mode
1. Click "Edit YAML" / "View Notebook" button
2. **View Mode**: See rendered charts and tables
3. **Edit Mode**: Modify the YAML configuration

### Switch Theme
1. Look for theme toggle in sidebar
2. Click to switch between light and dark mode

## Example Notebook: Stock Analysis

The included \`stock_analysis\` notebook shows:

**Exhibits:**
- **Price Overview** - 4 metric cards with key statistics
- **Daily Closing Prices** - Line chart showing price trends
- **Trading Volume** - Bar chart comparing volume by stock
- **Detailed Data** - Full data table with download option

**Filters:**
- **Date Range** - Select analysis period
- **Tickers** - Choose which stocks to analyze

## Troubleshooting

### Application won't start

Check dependencies:
```bash
pip list | grep -E "streamlit|pyspark|plotly|pyyaml|pandas"
```

### No data appears

Build Silver layer:
```bash
python test_build_silver.py
```

### Port in use

Use different port:
```bash
streamlit run app/ui/notebook_app_duckdb.py --server.port=8502
```

## Need Help?

See [RUNNING.md](RUNNING.md) for detailed documentation.
