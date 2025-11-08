# Quickstart Guide

Get de_Funk up and running in 5 minutes!

---

## Prerequisites

Before starting, ensure you have:

- **Python 3.8+** installed
- **pip** package manager
- **8GB+ RAM** recommended
- **Git** (to clone if needed)

---

## Step 1: Install Dependencies

Install the required Python packages:

```bash
pip install streamlit plotly pyyaml pandas duckdb pyarrow
```

Or install all dependencies at once:

```bash
pip install -r requirements.txt
```

**Expected packages:**
- `streamlit` - Web framework for the UI
- `plotly` - Interactive charts
- `pyyaml` - Configuration parsing
- `pandas` - Data manipulation
- `duckdb` - Fast analytics engine (10-100x faster than Spark)
- `pyarrow` - Parquet file support

**Note:** PySpark is optional and only needed for ETL pipelines, not for the UI.

---

## Step 2: Build Silver Layer Data

The application requires processed data in the Silver layer. Build it with:

```bash
python test_build_silver.py
```

This script:
1. Loads Bronze data from `/storage/bronze/`
2. Builds dimensional models (dimensions + facts)
3. Writes to `/storage/silver/company/`

**Expected output:**
```
✓ dim_company table created (X records)
✓ dim_exchange table created (Y records)
✓ fact_prices table created (Z records)
✓ prices_with_company view created
```

**Where's the Bronze data?**
- Bronze data comes from API ingestion (Polygon, BLS, Chicago)
- If you don't have Bronze data yet, see [Installation Guide](installation.md#initial-data-ingestion)
- For testing, sample data may be included in `/storage/bronze/`

---

## Step 3: Run the Application

Choose your preferred method:

### Option A: Quick Run Script (Recommended)

**Linux/Mac:**
```bash
./run_app.sh
```

**Windows or if shell script doesn't work:**
```bash
python run_app.py
```

This script:
- Sets up the Python environment
- Starts the Streamlit server
- Opens your browser automatically

### Option B: Direct Streamlit Command

```bash
streamlit run app/ui/notebook_app_duckdb.py
```

**Custom port:**
```bash
streamlit run app/ui/notebook_app_duckdb.py --server.port=8502
```

---

## Step 4: Explore the Application

Once started, you'll see:

```
You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

### What You'll See

1. **Server starts** at http://localhost:8501
2. **Browser opens** automatically (or navigate manually)
3. **Notebook Vault UI** appears with:
   - Sidebar navigation
   - Available notebooks
   - Filter controls
   - Theme toggle

---

## Using the Application

### Open a Notebook

1. Look in the **left sidebar** under "📚 Notebooks"
2. Browse available notebooks (organized by folder)
3. Click on **"stock_analysis"** to open it
4. The notebook opens in a new tab in the main area

**Available sample notebooks:**
- `stock_analysis.md` - Stock price and volume analysis
- `forecast_analysis.md` - Time series forecast results
- `aggregate_stock_analysis.md` - Market-level aggregates
- `stock_analysis_dynamic.md` - Advanced dynamic filters

### Apply Filters

Filters appear in the sidebar under **"🎛️ Filters"** when a notebook is open.

**Common filters:**
- **Date Range** - Select analysis period (start/end dates)
- **Tickers** - Multi-select which stocks to analyze
- **Thresholds** - Numeric filters (volume, price ranges)

**Behavior:**
- Filters apply automatically when changed
- Results update in real-time
- Filters are notebook-specific

### View Exhibits

Exhibits are visualizations in the main content area.

**Exhibit types:**
- **Metric Cards** - KPIs (avg price, total volume, etc.)
- **Line Charts** - Time series trends (prices over time)
- **Bar Charts** - Categorical comparisons (volume by ticker)
- **Data Tables** - Raw data with download option

### Toggle Edit/View Mode

Switch between viewing and editing notebooks:

1. Click **"Edit YAML"** / **"View Notebook"** button (top right)
2. **View Mode**: See rendered charts and tables
3. **Edit Mode**: Modify the YAML/Markdown configuration

**In Edit Mode:**
- Syntax highlighting for YAML/Markdown
- Edit filters, exhibits, and layout
- Save changes (future feature)

### Switch Theme

Toggle between light and dark mode:

1. Look for **theme toggle** in sidebar
2. Click to switch between **light** and **dark** mode
3. Professional theme with proper contrast

---

## Example: Stock Analysis Notebook

The included **`stock_analysis`** notebook demonstrates core features:

### Exhibits

1. **Price Overview** (Metric Cards)
   - Average close price
   - Total volume
   - Max high
   - Min low

2. **Daily Closing Prices** (Line Chart)
   - Price trends over time
   - Multi-ticker comparison
   - Interactive zoom/pan

3. **Trading Volume by Stock** (Bar Chart)
   - Volume comparison
   - Sortable by ticker
   - Hover for details

4. **Detailed Price Data** (Data Table)
   - Full dataset with all columns
   - Sortable and filterable
   - Download as CSV

### Filters

- **Date Range** - Select analysis period
- **Tickers** - Choose which stocks to analyze (multi-select)

**Try this:**
1. Set date range to last 30 days
2. Select 3-5 tickers (e.g., AAPL, GOOGL, MSFT)
3. Watch exhibits update automatically

---

## Understanding the Data Flow

```
┌──────────────────┐
│  External APIs   │  Polygon (stocks), BLS (macro), Chicago (city)
│  (Data Sources)  │
└────────┬─────────┘
         │
         ↓
┌──────────────────┐
│  Bronze Layer    │  Raw data stored as Parquet
│  (Raw Data)      │  /storage/bronze/{provider}/{table}/
└────────┬─────────┘
         │
         ↓
┌──────────────────┐
│  Silver Layer    │  Dimensional models (facts + dimensions)
│  (Curated Data)  │  /storage/silver/{model}/{table}/
└────────┬─────────┘
         │
         ↓
┌──────────────────┐
│  DuckDB Engine   │  Fast analytics (10-100x faster than Spark)
│  (Query Engine)  │  In-memory or persistent
└────────┬─────────┘
         │
         ↓
┌──────────────────┐
│  Streamlit UI    │  Interactive notebooks
│  (Visualization) │  http://localhost:8501
└──────────────────┘
```

---

## Next Steps

Now that you have de_Funk running, explore further:

### Learn More

- **[Architecture Overview](architecture-overview.md)** - Understand system design
- **[Installation Guide](installation.md)** - Complete setup for production
- **[Create a Notebook](how-to/create-a-notebook.md)** - Build custom dashboards

### Common Tasks

- **[Run the Pipeline](how-to/run-the-pipeline.md)** - Ingest new data
- **[Work with Session Data](how-to/work-with-session-data.md)** - Adhoc analysis
- **[Create a Model](how-to/create-a-model.md)** - Add dimensional models

---

## Troubleshooting

### Application Won't Start

**Check dependencies:**
```bash
pip list | grep -E "streamlit|duckdb|plotly|pyyaml|pandas"
```

**Reinstall if needed:**
```bash
pip install --upgrade streamlit plotly pyyaml pandas duckdb pyarrow
```

### No Data Appears

**Build Silver layer:**
```bash
python test_build_silver.py
```

**Check if Silver data exists:**
```bash
ls -lh storage/silver/company/
```

**Expected:**
- `dims/dim_company/` directory with Parquet files
- `dims/dim_exchange/` directory with Parquet files
- `facts/fact_prices/` directory with Parquet files

### Port Already in Use

**Use different port:**
```bash
streamlit run app/ui/notebook_app_duckdb.py --server.port=8502
```

**Kill existing process:**
```bash
# Find process using port 8501
lsof -ti:8501 | xargs kill -9
```

### "Module not found" Errors

**Ensure all dependencies are installed:**
```bash
pip install -r requirements.txt
```

**Activate virtual environment (if using):**
```bash
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate      # Windows
```

### DuckDB Errors

**Clear DuckDB cache:**
```bash
rm -rf .duckdb_cache
```

**Rebuild Silver layer:**
```bash
python test_build_silver.py
```

### Browser Doesn't Open

**Manually navigate to:**
```
http://localhost:8501
```

**Or check terminal output for the correct URL.**

### Slow Performance

**Possible causes:**
- Large datasets (filter to smaller date ranges)
- Low memory (close other applications)
- Old DuckDB version (upgrade: `pip install --upgrade duckdb`)

**Optimize:**
- Use date range filters to limit data
- Select fewer tickers
- Ensure DuckDB is using latest version (0.9.0+)

---

## Common Workflows

### Daily Workflow

1. **Start application**: `./run_app.sh`
2. **Open notebook**: Click "stock_analysis"
3. **Set filters**: Last 7 days, 5-10 tickers
4. **Analyze trends**: Review charts and metrics
5. **Download data**: Click download on data tables

### Development Workflow

1. **Edit notebook**: Toggle to Edit Mode
2. **Modify exhibits**: Update YAML configuration
3. **Save changes**: (future feature - currently manual)
4. **Refresh**: Reload page to see changes

### Data Refresh Workflow

1. **Run data pipeline**: `python scripts/run_company_data_pipeline.py --days 7`
2. **Rebuild Silver**: `python test_build_silver.py`
3. **Restart app**: `./run_app.sh`
4. **Verify new data**: Check date ranges in filters

---

## Performance Tips

### For Faster Analytics

1. **Use DuckDB** (default) - 10-100x faster than Spark for analytics
2. **Filter early** - Apply date and ticker filters to reduce data
3. **Latest version** - Keep DuckDB updated (`pip install --upgrade duckdb`)
4. **Memory** - 8GB+ RAM recommended for large datasets

### For Large Datasets

1. **Partition data** - Bronze layer auto-partitions by date
2. **Date filters** - Always filter to relevant date ranges
3. **Ticker limits** - Select specific tickers vs "all"
4. **Paginate tables** - Use built-in Streamlit pagination

---

## Architecture Overview (Quick)

**Bronze Layer:**
- Raw data from APIs
- Stored as Parquet (partitioned)
- `/storage/bronze/{provider}/{table}/`

**Silver Layer:**
- Dimensional models (facts + dimensions)
- YAML-driven transformations
- `/storage/silver/{model}/{table}/`

**DuckDB Engine:**
- Fast in-memory analytics
- SQL queries with Parquet backend
- 10-100x faster than Spark for UI

**Streamlit UI:**
- Markdown-based notebooks
- Dynamic filters
- Interactive exhibits

**For complete details:** See [Architecture Overview](architecture-overview.md)

---

## Need Help?

**Documentation:**
- [Installation Guide](installation.md) - Detailed setup
- [Architecture Overview](architecture-overview.md) - System design
- [How-To Guides](how-to/README.md) - Step-by-step tutorials

**Common Issues:**
- Check troubleshooting section above
- Review terminal output for error messages
- Verify data exists in `/storage/silver/`

**Still stuck?**
- Review [RUNNING.md](/home/user/de_Funk/RUNNING.md) for additional details
- Check [QUICKSTART.md](/home/user/de_Funk/QUICKSTART.md) for the original guide

---

## What's Next?

Congratulations! You now have de_Funk running.

**Continue learning:**
1. **[Architecture Overview](architecture-overview.md)** - Understand how it all works
2. **[Create a Notebook](how-to/create-a-notebook.md)** - Build your own dashboard
3. **[Run the Pipeline](how-to/run-the-pipeline.md)** - Ingest fresh data
4. **[Work with Session Data](how-to/work-with-session-data.md)** - Adhoc analysis

**Happy analyzing!** 🚀
