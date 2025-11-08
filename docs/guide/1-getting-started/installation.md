# Installation Guide

Complete installation and configuration instructions for production deployment of de_Funk.

---

## Overview

This guide covers:

1. **Environment setup** - Python, virtual environments
2. **Dependency installation** - Required packages
3. **Configuration** - API keys, storage, database
4. **Initial data ingestion** - Getting your first data
5. **Verification** - Testing the installation
6. **Troubleshooting** - Common issues

**Time Required:** 30-45 minutes

---

## Prerequisites

### System Requirements

**Hardware:**
- **CPU:** 2+ cores (4+ recommended)
- **RAM:** 8GB minimum (16GB+ recommended for large datasets)
- **Disk:** 10GB+ free space (depends on data volume)

**Operating System:**
- Linux (Ubuntu 18.04+, CentOS 7+)
- macOS (10.14+)
- Windows 10/11 (WSL2 recommended)

**Software:**
- **Python 3.8+** (3.10 recommended)
- **pip** 21.0+
- **Git** (for cloning repository)

### Required for Data Ingestion and ETL

**For Data Ingestion and Model Building (Required):**
- **Java 8 or 11** (required for PySpark)
- **PySpark 3.4+** (required for data ingestion and model transformations)

**For Development:**
- **Code editor** (VS Code, PyCharm, etc.)
- **Virtual environment manager** (venv, conda, poetry)

---

## Step 1: Clone Repository

```bash
# Clone the repository
git clone https://github.com/your-org/de_Funk.git

# Navigate to directory
cd de_Funk

# Check directory structure
ls -la
```

**Expected structure:**
```
de_Funk/
├── app/
├── configs/
├── core/
├── datapipelines/
├── docs/
├── models/
├── scripts/
├── storage/
├── requirements.txt
└── run_app.sh
```

---

## Step 2: Python Environment Setup

### Option A: Using venv (Recommended)

```bash
# Create virtual environment
python3 -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Verify activation
which python  # Should show venv/bin/python
```

### Option B: Using conda

```bash
# Create conda environment
conda create -n de_funk python=3.10

# Activate
conda activate de_funk

# Verify
python --version  # Should show 3.10.x
```

### Option C: Using poetry

```bash
# Install poetry (if not installed)
curl -sSL https://install.python-poetry.org | python3 -

# Create environment
poetry install

# Activate
poetry shell
```

---

## Step 3: Install Dependencies

### Core Dependencies (Required)

```bash
# Install from requirements.txt
pip install -r requirements.txt
```

**Core packages installed:**
- `streamlit>=1.28.0` - Web framework
- `pandas>=2.0.0` - Data manipulation
- `duckdb>=0.9.0` - Analytics engine
- `plotly>=5.17.0` - Visualization
- `pyyaml>=6.0` - Configuration
- `pyarrow>=13.0.0` - Parquet support
- `markdown>=3.4.0` - Notebook rendering

### Forecasting Dependencies (Optional)

If you plan to use forecasting features:

```bash
pip install statsmodels>=0.14.0 prophet>=1.1.5 scikit-learn>=1.3.0
```

**Forecasting packages:**
- `statsmodels` - ARIMA models
- `prophet` - Facebook Prophet
- `scikit-learn` - Random Forest, other ML models

### Spark Dependencies (Required)

Spark is required for data ingestion and model building:

```bash
# Install PySpark
pip install pyspark>=3.4.0

# Verify installation
pyspark --version
```

**Note:** Spark requires Java 8 or 11. Install Java first:

```bash
# Ubuntu/Debian
sudo apt-get install openjdk-11-jdk

# macOS
brew install openjdk@11

# Verify
java -version
```

### Verify Installation

```bash
# Check all packages
pip list | grep -E "streamlit|duckdb|plotly|pyyaml|pandas"

# Expected output:
# duckdb         0.9.2
# pandas         2.1.0
# plotly         5.17.0
# pyyaml         6.0.1
# streamlit      1.28.1
```

---

## Step 4: Configuration

### A. API Keys Setup

de_Funk integrates with external APIs. Set up API keys for the data sources you need.

#### Polygon API (Stock Market Data)

**Required for:** Company model (stocks, prices, news)

**Get API key:**
1. Sign up at https://polygon.io/
2. Free tier: 5 API calls/minute
3. Paid tier: Unlimited (recommended for production)

**Set environment variable:**

```bash
# Linux/Mac
export POLYGON_API_KEY="your_polygon_api_key_here"

# Windows
set POLYGON_API_KEY=your_polygon_api_key_here

# Add to .bashrc/.zshrc for persistence
echo 'export POLYGON_API_KEY="your_key_here"' >> ~/.bashrc
source ~/.bashrc
```

**Or use .env file:**

```bash
# Create .env file in project root
cat > .env << EOF
POLYGON_API_KEY=your_polygon_api_key_here
EOF

# Ensure .env is in .gitignore (should already be)
echo '.env' >> .gitignore
```

#### BLS API (Economic Indicators)

**Required for:** Macro model (employment, CPI, etc.)

**Get API key:**
1. Register at https://www.bls.gov/developers/
2. Free tier: 500 requests/day
3. API key increases limit to 500 requests/day with higher rate limits

**Set environment variable:**

```bash
export BLS_API_KEY="your_bls_api_key_here"
```

**Note:** BLS API key is optional for small-scale use.

#### Chicago Data Portal

**Required for:** City finance model

**No API key required!** Chicago Data Portal is open access.

### B. Storage Configuration

Configure storage paths and formats.

**Default configuration:** `configs/storage.json`

```json
{
  "bronze": {
    "root": "storage/bronze",
    "format": "parquet",
    "partitioning": "date"
  },
  "silver": {
    "root": "storage/silver",
    "format": "parquet"
  },
  "duckdb": {
    "path": "storage/duckdb/analytics.db",
    "memory_limit": "8GB"
  }
}
```

**Customization:**

```bash
# Edit storage configuration
nano configs/storage.json

# Or copy and customize
cp configs/storage.json configs/storage.local.json
# Edit storage.local.json
```

**Storage path options:**

1. **Local storage** (default):
   - `storage/bronze/` - Raw data
   - `storage/silver/` - Dimensional models
   - Suitable for single-node deployments

2. **Network storage**:
   - Replace paths with network mounts
   - Example: `/mnt/nfs/de_funk/bronze/`

3. **Cloud storage** (future):
   - S3: `s3://bucket/bronze/`
   - Azure Blob: `abfs://container/bronze/`
   - GCS: `gs://bucket/bronze/`

### C. Database Configuration

#### DuckDB (Default)

DuckDB requires minimal configuration. Defaults work for most use cases.

**Configuration in storage.json:**

```json
{
  "duckdb": {
    "path": "storage/duckdb/analytics.db",
    "memory_limit": "8GB",
    "threads": 4
  }
}
```

**Adjust memory_limit based on available RAM:**
- 8GB RAM system: `"memory_limit": "4GB"`
- 16GB RAM system: `"memory_limit": "8GB"`
- 32GB+ RAM system: `"memory_limit": "16GB"`

**DuckDB modes:**

1. **In-memory** (default for UI):
   - Fastest performance
   - Data loaded from Parquet on startup
   - No persistent database file

2. **Persistent**:
   - Database file written to disk
   - Faster subsequent startups
   - Set `"path": "storage/duckdb/analytics.db"`

**Create storage directories:**

```bash
mkdir -p storage/bronze storage/silver storage/duckdb
```

#### Spark (Optional)

Only configure if using Spark for ETL pipelines.

**Spark configuration:** `configs/spark.yaml`

```yaml
spark:
  app_name: de_funk_etl
  master: local[*]  # Or spark://host:port for cluster
  config:
    spark.executor.memory: 4g
    spark.driver.memory: 2g
    spark.sql.shuffle.partitions: 200
```

**Cluster mode:**
```yaml
spark:
  master: spark://master:7077
  config:
    spark.executor.instances: 4
    spark.executor.cores: 4
    spark.executor.memory: 8g
```

### D. Model Configuration

Models are configured in `configs/models/`. Review and customize as needed.

**Available models:**
- `company.yaml` - Stock market data
- `forecast.yaml` - Time series forecasts
- `macro.yaml` - Economic indicators
- `city_finance.yaml` - Municipal finance
- `core.yaml` - Shared dimensions

**Example customization:**

```bash
# Edit company model
nano configs/models/company.yaml

# Customize schema, measures, graph transformations
```

---

## Step 5: Initial Data Ingestion

### Option A: Quick Test (Recommended for First Install)

Use the test build script with sample data:

```bash
# Build Silver layer from existing Bronze data (if available)
python test_build_silver.py
```

**Expected output:**
```
Building Silver layer...
✓ dim_company created (X records)
✓ dim_exchange created (Y records)
✓ fact_prices created (Z records)
✓ prices_with_company view created
Silver layer build complete!
```

**If no Bronze data exists, skip to Option B.**

### Option B: Full Data Ingestion

Ingest data from external APIs:

#### Step 1: Ingest Company Data (Stocks)

```bash
# Ingest last 30 days for 10 tickers (testing)
python scripts/run_company_data_pipeline.py --days 30 --max-tickers 10

# Or ingest last 90 days for all available tickers
python scripts/run_company_data_pipeline.py --days 90
```

**Parameters:**
- `--days N` - Number of recent days to ingest
- `--from DATE --to DATE` - Specific date range
- `--max-tickers N` - Limit number of tickers (default: all)
- `--no-news` - Skip news ingestion (faster)

**Expected output:**
```
Starting company data pipeline...
Fetching tickers...
Fetching price data...
  • AAPL: 30 days
  • GOOGL: 30 days
  ...
Writing to Bronze layer...
Pipeline complete! (10 tickers, 300 records)
```

**Verify Bronze layer:**
```bash
ls -lh storage/bronze/polygon/
# Should see: prices_daily/, ref_ticker/, exchanges/
```

#### Step 2: Build Silver Layer

Transform Bronze → Silver:

```bash
python test_build_silver.py
```

**Or use the full pipeline:**
```bash
python scripts/run_full_pipeline.py --days 30 --max-tickers 10
```

**Verify Silver layer:**
```bash
ls -lh storage/silver/company/
# Should see: dims/, facts/
```

#### Step 3: Run Forecasts (Optional)

Generate time series forecasts:

```bash
# Run forecasts for all tickers
python scripts/run_forecasts.py

# Or for specific tickers
python scripts/run_forecasts.py --tickers AAPL,GOOGL,MSFT
```

**Expected output:**
```
Running forecasts...
  • AAPL: ARIMA (MAE: 1.23), Prophet (MAE: 1.45)
  • GOOGL: ARIMA (MAE: 2.34), Prophet (MAE: 2.56)
  ...
Forecasts complete!
```

### Option C: One-Command Full Pipeline

Ingest data + build Silver + run forecasts in one command:

```bash
# Complete pipeline (testing with 10 tickers)
python scripts/run_full_pipeline.py --days 30 --max-tickers 10

# Production (all tickers, 90 days)
python scripts/run_full_pipeline.py --days 90
```

**This command:**
1. Ingests data from Polygon API
2. Writes to Bronze layer
3. Builds Silver layer models
4. Runs forecast models
5. Writes forecast results

**Time estimate:**
- 10 tickers, 30 days: ~5-10 minutes
- All tickers, 90 days: ~30-60 minutes (depends on API rate limits)

---

## Step 6: Verification

### Test 1: Check Storage

```bash
# Check Bronze layer
ls -lh storage/bronze/polygon/prices_daily/
# Should see partitioned directories: trade_date=YYYY-MM-DD/

# Check Silver layer
ls -lh storage/silver/company/facts/fact_prices/
# Should see Parquet files or partitioned directories

# Check file sizes (should be reasonable)
du -sh storage/bronze/
du -sh storage/silver/
```

### Test 2: Run Application

```bash
# Start UI
./run_app.sh

# Or directly
streamlit run app/ui/notebook_app_duckdb.py
```

**Check:**
1. Browser opens to http://localhost:8501
2. UI loads without errors
3. Sidebar shows available notebooks
4. Click "stock_analysis" notebook
5. Filters appear in sidebar
6. Exhibits render (charts, tables)

### Test 3: Query Data Programmatically

```python
# test_installation.py
from core.context import RepoContext
from models.api.session import UniversalSession

# Initialize context
ctx = RepoContext.from_repo_root(connection_type="duckdb")

# Create session
session = UniversalSession(
    connection=ctx.connection,
    storage_cfg=ctx.storage,
    repo_root=ctx.repo
)

# Load model
session.load_model("company")

# Query data
df = session.get_table("company", "fact_prices")
print(f"✓ fact_prices: {len(df)} rows")

# Get dimension
dim_df = session.get_dimension_df("company", "dim_company")
print(f"✓ dim_company: {len(dim_df)} rows")

print("Installation verified!")
```

**Run test:**
```bash
python test_installation.py
```

**Expected output:**
```
✓ fact_prices: 300 rows
✓ dim_company: 10 rows
Installation verified!
```

---

## Step 7: Production Deployment

### A. Systemd Service (Linux)

Create a systemd service for automatic startup:

```bash
# Create service file
sudo nano /etc/systemd/system/de_funk.service
```

**Service configuration:**
```ini
[Unit]
Description=de_Funk Analytics Platform
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/de_Funk
Environment="PATH=/path/to/de_Funk/venv/bin"
Environment="POLYGON_API_KEY=your_key_here"
ExecStart=/path/to/de_Funk/venv/bin/streamlit run app/ui/notebook_app_duckdb.py --server.port=8501
Restart=always

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable de_funk
sudo systemctl start de_funk
sudo systemctl status de_funk
```

### B. Docker Deployment (Optional)

Create a Dockerfile:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8501

# Run application
CMD ["streamlit", "run", "app/ui/notebook_app_duckdb.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

**Build and run:**
```bash
# Build image
docker build -t de_funk:latest .

# Run container
docker run -d \
  -p 8501:8501 \
  -v $(pwd)/storage:/app/storage \
  -e POLYGON_API_KEY="your_key_here" \
  --name de_funk \
  de_funk:latest

# Check logs
docker logs -f de_funk
```

### C. Scheduled Data Refresh

Set up cron jobs for automatic data updates:

```bash
# Edit crontab
crontab -e

# Add daily refresh (6 AM)
0 6 * * * cd /path/to/de_Funk && /path/to/venv/bin/python scripts/run_full_pipeline.py --days 7 >> /var/log/de_funk/pipeline.log 2>&1

# Add weekly full refresh (Sunday 2 AM)
0 2 * * 0 cd /path/to/de_Funk && /path/to/venv/bin/python scripts/run_full_pipeline.py --days 90 >> /var/log/de_funk/pipeline.log 2>&1
```

**Create log directory:**
```bash
sudo mkdir -p /var/log/de_funk
sudo chown your_username:your_username /var/log/de_funk
```

### D. Nginx Reverse Proxy (Optional)

Expose UI via Nginx with SSL:

```nginx
# /etc/nginx/sites-available/de_funk
server {
    listen 80;
    server_name analytics.yourdomain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Enable and restart:**
```bash
sudo ln -s /etc/nginx/sites-available/de_funk /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**Add SSL with Let's Encrypt:**
```bash
sudo certbot --nginx -d analytics.yourdomain.com
```

---

## Troubleshooting

### Installation Issues

#### "Python not found"

```bash
# Check Python installation
python3 --version

# Install Python (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install python3.10 python3.10-venv python3-pip

# Install Python (macOS)
brew install python@3.10
```

#### "pip install fails"

```bash
# Upgrade pip
pip install --upgrade pip

# Install with verbose output
pip install -v streamlit

# Try with --no-cache-dir
pip install --no-cache-dir streamlit
```

#### "DuckDB install fails"

DuckDB requires a C++ compiler. Install build tools:

```bash
# Ubuntu/Debian
sudo apt-get install build-essential

# macOS
xcode-select --install

# Then retry
pip install duckdb
```

### Configuration Issues

#### "API key not found"

```bash
# Verify environment variable
echo $POLYGON_API_KEY

# If empty, set it
export POLYGON_API_KEY="your_key_here"

# Add to shell config for persistence
echo 'export POLYGON_API_KEY="your_key_here"' >> ~/.bashrc
source ~/.bashrc
```

#### "Storage path not found"

```bash
# Create storage directories
mkdir -p storage/bronze storage/silver storage/duckdb

# Check permissions
ls -ld storage/
# Should be writable by current user
```

### Data Ingestion Issues

#### "API rate limit exceeded"

```bash
# Use smaller --max-tickers
python scripts/run_company_data_pipeline.py --days 7 --max-tickers 5

# Wait and retry (rate limits reset)
# Upgrade to paid Polygon tier for higher limits
```

#### "No data in Bronze layer"

```bash
# Check API key
echo $POLYGON_API_KEY

# Run with debug output
python scripts/run_company_data_pipeline.py --days 7 --max-tickers 5 --verbose

# Check network connectivity
curl https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-10?apiKey=$POLYGON_API_KEY
```

#### "Silver layer build fails"

```bash
# Check Bronze data exists
ls -lh storage/bronze/polygon/

# Run with error details
python test_build_silver.py --verbose

# Check model configuration
cat configs/models/company.yaml
```

### Runtime Issues

#### "UI won't start"

```bash
# Check port availability
lsof -i :8501

# Kill existing process if needed
lsof -ti:8501 | xargs kill -9

# Use different port
streamlit run app/ui/notebook_app_duckdb.py --server.port=8502
```

#### "No notebooks shown"

```bash
# Check notebook files exist
ls -lh configs/notebooks/

# Verify notebook format
cat configs/notebooks/stock_analysis.md

# Check console for errors
streamlit run app/ui/notebook_app_duckdb.py --logger.level=debug
```

#### "Slow query performance"

```bash
# Check dataset size
du -sh storage/silver/company/

# Optimize DuckDB memory
# Edit configs/storage.json, increase memory_limit

# Use date filters to limit data
# In UI, select smaller date ranges

# Upgrade DuckDB
pip install --upgrade duckdb
```

#### "Out of memory"

```bash
# Check available memory
free -h

# Reduce DuckDB memory limit
# Edit configs/storage.json:
# "memory_limit": "4GB"  (or lower)

# Close other applications

# Limit dataset size with filters
```

### Network Issues

#### "Connection refused"

```bash
# Check if process is running
ps aux | grep streamlit

# Check firewall
sudo ufw allow 8501

# Check binding address
streamlit run app/ui/notebook_app_duckdb.py --server.address=0.0.0.0
```

#### "Reverse proxy not working"

```bash
# Check Nginx configuration
sudo nginx -t

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log

# Verify proxy settings in Nginx config
```

---

## Performance Tuning

### DuckDB Optimization

```json
{
  "duckdb": {
    "memory_limit": "16GB",
    "threads": 8,
    "temp_directory": "/tmp/duckdb"
  }
}
```

**Recommendations:**
- `memory_limit`: 50-75% of available RAM
- `threads`: Number of CPU cores
- `temp_directory`: Fast SSD if available

### Storage Optimization

```bash
# Compress older partitions
find storage/bronze -name "*.parquet" -mtime +30 -exec gzip {} \;

# Archive old data
tar -czf archive_2023.tar.gz storage/bronze/polygon/prices_daily/trade_date=2023-*

# Delete archived data
rm -rf storage/bronze/polygon/prices_daily/trade_date=2023-*
```

### Query Optimization

- **Use filters** - Always filter by date and ticker
- **Limit results** - Use LIMIT in queries
- **Partition data** - Ensure Bronze/Silver are partitioned by date
- **Update DuckDB** - Keep DuckDB at latest version

---

## Next Steps

Your de_Funk installation is complete!

### Learn More

- **[Quickstart Guide](quickstart.md)** - Get running in 5 minutes
- **[Architecture Overview](architecture-overview.md)** - Understand the system
- **[How-To Guides](how-to/README.md)** - Common tasks and workflows

### Start Using

- **[Use the UI](how-to/use-the-ui.md)** - Navigate the interface
- **[Create a Notebook](how-to/create-a-notebook.md)** - Build dashboards
- **[Work with Session Data](how-to/work-with-session-data.md)** - Adhoc analysis

### Extend the Platform

- **[Create a Model](how-to/create-a-model.md)** - Add new data models
- **[Create a Facet](how-to/create-a-facet.md)** - Add data sources
- **[Run the Pipeline](how-to/run-the-pipeline.md)** - Automate data ingestion

---

## Support Resources

**Documentation:**
- [QUICKSTART.md](/home/user/de_Funk/QUICKSTART.md) - Quick start guide
- [RUNNING.md](/home/user/de_Funk/RUNNING.md) - Running the application
- [PIPELINE_GUIDE.md](/home/user/de_Funk/PIPELINE_GUIDE.md) - Pipeline details

**Community:**
- GitHub Issues - Report bugs
- Discussions - Ask questions
- Wiki - Community guides

---

**Installation complete!** 🎉

Continue to: [Quickstart Guide](quickstart.md) →
