# Alpha Vantage Setup Guide

Quick guide to get started with Alpha Vantage data provider for de_Funk.

## 1. Get Your API Key (2 minutes)

### Free Tier
1. Visit: https://www.alphavantage.co/support/#api-key
2. Fill in your email
3. Copy your API key (looks like: `ABCD1234EFGH5678`)

**Free Tier Limits:**
- 25 API calls per day
- 5 API calls per minute
- Perfect for testing and development

### Premium Tier (Optional)
- 75 calls/minute
- 750 calls/day
- Visit: https://www.alphavantage.co/premium/

## 2. Configure Environment (1 minute)

Add your API key to `.env` file:

```bash
# Alpha Vantage API Key
ALPHA_VANTAGE_API_KEYS=your_actual_api_key_here

# For multiple keys (premium tier - key rotation):
# ALPHA_VANTAGE_API_KEYS=key1,key2,key3
```

**Note:** Make sure `.env` is in `.gitignore` (it already is)

## 3. Test the Integration (5 minutes)

Run the test script to verify everything works:

```bash
# Basic test (2 tickers, 90 days of history)
python -m scripts.test_alpha_vantage_ingestion

# Custom tickers
python -m scripts.test_alpha_vantage_ingestion --tickers AAPL MSFT GOOGL

# Just reference data (faster)
python -m scripts.test_alpha_vantage_ingestion --skip-prices

# Just prices (if you already have reference data)
python -m scripts.test_alpha_vantage_ingestion --skip-reference
```

**What This Does:**
- ✅ Validates your API key
- ✅ Fetches company overview (sector, industry, PE ratio, etc.)
- ✅ Fetches daily OHLCV prices (last 90 days by default)
- ✅ Writes to bronze layer: `storage/bronze/securities_*`
- ✅ Shows sample data

**Expected Output:**
```
🚀 Alpha Vantage Ingestion Test
================================================
✓ Found 1 Alpha Vantage API key(s)
✓ Spark session created

📋 STEP 1: Ingesting Reference Data
Tickers: AAPL, MSFT
...
✅ SUCCESS: Reference data written to: storage/bronze/securities_reference/

📈 STEP 2: Ingesting Daily Prices
Tickers: AAPL, MSFT
...
✅ SUCCESS: Prices written to: storage/bronze/securities_prices_daily/

✅ ALL TESTS PASSED
```

## 4. What Data You Get

### Reference Data (`securities_reference`)
From Alpha Vantage **OVERVIEW** endpoint:

**Basic Info:**
- ticker, security_name, asset_type
- exchange_code, currency, sector, industry

**Fundamental Data:**
- market_cap, shares_outstanding
- pe_ratio, peg_ratio, eps
- book_value, dividend_yield
- week_52_high, week_52_low

**Note:** CIK field will be NULL (Alpha Vantage doesn't provide SEC identifiers)

### Price Data (`securities_prices_daily`)
From Alpha Vantage **TIME_SERIES_DAILY_ADJUSTED** endpoint:

**OHLCV Data:**
- trade_date, ticker, asset_type
- open, high, low, close, volume
- volume_weighted (calculated as (H+L+C)/3)

**Alpha Vantage Specific:**
- adjusted_close (split/dividend adjusted)
- dividend_amount (on ex-dividend dates)
- split_coefficient (on split dates)

## 5. Build Silver Models

Once bronze data is ingested, build the silver layer:

```bash
# Build stocks model (uses bronze data from either Polygon OR Alpha Vantage)
python -m scripts.rebuild_model --model stocks

# Build company model
python -m scripts.rebuild_model --model company
```

## 6. Query and Analyze

### Using Universal Session
```python
from core.session.universal_session import UniversalSession

session = UniversalSession(backend="duckdb")

# Query prices
df = session.query("""
    SELECT ticker, trade_date, close, adjusted_close, volume
    FROM stocks.fact_stock_prices
    WHERE ticker = 'AAPL'
    AND trade_date >= '2024-01-01'
    ORDER BY trade_date DESC
    LIMIT 10
""")
```

### Using Python Measures
```python
from models.api.registry import get_model_registry

registry = get_model_registry()
model = registry.get_model("stocks")

# Calculate Sharpe ratio (Python measure)
sharpe = model.calculate_measure(
    "sharpe_ratio",
    ticker="AAPL",
    window_days=252,
    risk_free_rate=0.045
)

# Simple aggregations (YAML measure)
avg_price = model.calculate_measure("avg_close_price", ticker="AAPL")
```

## Rate Limit Management

### Free Tier Strategy (5 calls/minute)
- **Reference Data:** ~1 minute per 5 tickers
- **Prices:** ~1 minute per 5 tickers
- **Example:** 10 tickers = 2 minutes for reference + 2 minutes for prices = 4 minutes total

### Best Practices
1. **Start Small:** Test with 2-3 tickers first
2. **Sequential Processing:** Use `use_concurrent=False` (default)
3. **Daily Limits:** Track your 25 calls/day on free tier
4. **Batch Wisely:** Ingest reference data separately from prices

### If You Hit Rate Limits
```
Error: API call frequency is 5 calls per minute and 25 calls per day
```

**Solutions:**
- Wait 1 minute and retry
- Reduce number of tickers
- Upgrade to premium tier ($50/month for 75 calls/min)

## Comparison: Alpha Vantage vs Polygon

| Feature | Alpha Vantage | Polygon |
|---------|---------------|---------|
| **Free Tier** | 25 calls/day | 5 calls/min |
| **Rate Limit** | 5 calls/min | Much higher |
| **CIK (SEC ID)** | ❌ No | ✅ Yes |
| **Fundamentals** | ✅ PE ratio, dividends | ❌ Limited |
| **Historical Data** | ✅ 20+ years | ✅ 2+ years |
| **Split/Dividend** | ✅ Yes | ✅ Yes |
| **Technical Indicators** | ✅ Built-in | ❌ Calculate yourself |
| **Options Greeks** | ❌ No | ✅ Yes |

## Hybrid Approach (Recommended)

Use **both** providers for complementary data:

```python
# 1. Get reference data from Polygon (includes CIK)
polygon_ingestor.ingest_reference_data(tickers=['AAPL', 'MSFT'])

# 2. Get prices from Alpha Vantage (free tier, long history)
alpha_vantage_ingestor.ingest_prices(
    tickers=['AAPL', 'MSFT'],
    date_from='2020-01-01',
    outputsize='full'
)

# 3. Bronze tables merge automatically (same schema)
# 4. Silver models work with combined data
```

**Benefits:**
- ✅ CIK from Polygon for company linkage
- ✅ Free historical prices from Alpha Vantage
- ✅ Fundamentals from Alpha Vantage (PE ratio, etc.)
- ✅ Best of both worlds

## Troubleshooting

### API Key Not Found
```
❌ ERROR: No Alpha Vantage API key found!
```
**Fix:** Add `ALPHA_VANTAGE_API_KEYS=your_key` to `.env` file

### Invalid API Key
```
Error: Invalid API call or API key
```
**Fix:**
1. Verify key is correct (no spaces/typos)
2. Check key is active at https://www.alphavantage.co/support/#api-key
3. Get new key if needed

### Rate Limit Exceeded
```
Note: API call frequency is 5 calls per minute
```
**Fix:**
1. Wait 60 seconds
2. Reduce number of tickers
3. Use `--skip-prices` or `--skip-reference` flags

### No Data Returned
```
Warning: Alpha Vantage error for AAPL: {'Note': 'Thank you for using Alpha Vantage!'}
```
**Fix:**
1. Check ticker symbol is valid
2. Try different ticker (some may not be available)
3. Wait a few seconds and retry

## Next Steps

1. ✅ Get API key and configure `.env`
2. ✅ Run test script: `python -m scripts.test_alpha_vantage_ingestion`
3. ✅ Verify bronze data exists: `ls storage/bronze/securities_*`
4. ✅ Build silver models: `python -m scripts.rebuild_model --model stocks`
5. ✅ Query and analyze data
6. 🚀 Build dashboards and analytics

## Support

- **Alpha Vantage Docs:** https://www.alphavantage.co/documentation/
- **de_Funk Docs:** See `CLAUDE.md` for full architecture
- **Issues:** Report at GitHub Issues
- **API Status:** https://status.alphavantage.co/

---

**Ready to go!** Run the test script and start ingesting data. 🚀
