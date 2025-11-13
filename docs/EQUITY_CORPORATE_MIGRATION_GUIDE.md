# Migration Guide: Company → Equity + Corporate

**Version:** 1.0
**Date:** 2025-11-13
**Status:** Implemented - company model deprecated

---

## 🎯 Overview

The `company` model has been split into two focused models:
- **`equity`** - Trading instruments (tickers, prices, technicals)
- **`corporate`** - Legal entities (companies, fundamentals, SEC filings)

This guide helps you migrate existing code to use the new models.

---

## 📊 Quick Reference

### Model Mapping

| Old (company) | New | Model |
|---------------|-----|-------|
| `fact_prices` | `fact_equity_prices` | equity |
| `fact_news` | `fact_equity_news` | equity |
| `dim_company` | `dim_equity` | equity |
| `dim_exchange` | `dim_exchange` | equity |
| `prices_with_company` | `equity_prices_with_company` | equity |
| N/A (new) | `fact_equity_technicals` | equity |
| N/A (new) | `dim_corporate` | corporate |
| N/A (new) | `fact_sec_filings` | corporate |
| N/A (new) | `fact_financials` | corporate |

### Model Import Changes

```python
# OLD
from models.implemented.company.model import CompanyModel

# NEW
from models.implemented.equity.model import EquityModel
from models.implemented.corporate.model import CorporateModel
```

### Measure Names (unchanged)

All measure names remain the same:
- `avg_close_price`
- `total_volume`
- `volume_weighted_index`
- `market_cap_weighted_index`
- etc.

---

## 🔄 Migration Steps

### 1. Update Model Instantiation

**Before:**
```python
from models.implemented.company.model import CompanyModel

# Create company model
company = CompanyModel(connection, storage, repo)

# Calculate measures
result = company.calculate_measure_by_ticker('avg_close_price', limit=10)
```

**After:**
```python
from models.implemented.equity.model import EquityModel
from models.implemented.corporate.model import CorporateModel

# Create equity model (for price/trading data)
equity = EquityModel(connection, storage, repo)

# Same API - no changes needed!
result = equity.calculate_measure_by_ticker('avg_close_price', limit=10)

# Create corporate model (for fundamentals - future)
corporate = CorporateModel(connection, storage, repo)
```

**Key point:** The API is identical! Just change the import.

---

### 2. Update Table Access

**Before:**
```python
company = CompanyModel(...)

# Get prices
prices = company.get_table('fact_prices')

# Get news
news = company.get_table('fact_news')

# Get canonical view
analytics = company.get_table('prices_with_company')
```

**After (Option A - Use new table names):**
```python
equity = EquityModel(...)

# Get prices - use new table name
prices = equity.get_table('fact_equity_prices')

# Get news
news = equity.get_table('fact_equity_news')

# Get canonical view
analytics = equity.get_table('equity_prices_with_company')
```

**After (Option B - Use legacy compatibility):**
```python
equity = EquityModel(...)

# OLD table names still work! (legacy compatibility built-in)
prices = equity.get_table('fact_prices')  # ← Auto-mapped to fact_equity_prices
news = equity.get_table('fact_news')      # ← Auto-mapped to fact_equity_news
analytics = equity.get_table('prices_with_company')  # ← Auto-mapped
```

**Recommendation:** Use Option B during migration, then gradually move to Option A.

---

### 3. Update Model Registry

**Before:**
```python
from models.registry import ModelRegistry

registry = ModelRegistry(connection, storage, repo)
company_model = registry.load_model('company')
```

**After:**
```python
from models.registry import ModelRegistry

registry = ModelRegistry(connection, storage, repo)

# Load equity model
equity_model = registry.load_model('equity')

# Load corporate model
corporate_model = registry.load_model('corporate')

# Legacy: company still works (loads equity with compatibility layer)
legacy_model = registry.load_model('company')  # Still works!
```

---

### 4. Update Forecast Models

**Before:**
```python
# forecast/company_forecast_model.py
def get_source_model_name(self) -> str:
    return 'company'

def get_source_table_name(self) -> str:
    return 'fact_prices'
```

**After:**
```python
# forecast/company_forecast_model.py
def get_source_model_name(self) -> str:
    return 'equity'  # ← Changed from 'company'

def get_source_table_name(self) -> str:
    return 'fact_equity_prices'  # ← Changed from 'fact_prices'
```

**Note:** The forecast model name can stay `CompanyForecastModel` for backward compatibility, but it now sources from the equity model.

---

### 5. Update Notebooks and Scripts

**Before:**
```python
# scripts/run_company_pipeline.py
from models.implemented.company.model import CompanyModel

model = CompanyModel(spark, model_cfg, storage_cfg)
dims, facts = model.build()

# Use fact_prices
prices = facts['fact_prices']
```

**After:**
```python
# scripts/run_equity_pipeline.py
from models.implemented.equity.model import EquityModel

model = EquityModel(spark, model_cfg, storage_cfg)
dims, facts = model.build()

# Use fact_equity_prices (or fact_prices with legacy compatibility)
prices = facts['fact_equity_prices']
```

---

### 6. Update Streamlit Exhibits

**Before:**
```yaml
# notebooks/stock_analysis.yaml
exhibits:
  - id: price_chart
    source: company.fact_prices
    ...
```

**After:**
```yaml
# notebooks/stock_analysis.yaml
exhibits:
  - id: price_chart
    source: equity.fact_equity_prices  # ← Changed model and table
    ...
```

**Alternative (legacy compatibility):**
```yaml
exhibits:
  - id: price_chart
    source: equity.fact_prices  # ← Old table name still works!
    ...
```

---

## 🆕 New Features

### 1. Technical Indicators

```python
from models.implemented.equity.model import EquityModel

equity = EquityModel(connection, storage, repo)

# Get technical indicators (NEW!)
technicals = equity.get_equity_technicals(
    tickers=['AAPL', 'MSFT'],
    start_date='2024-01-01',
    end_date='2024-01-31'
)

# Columns: rsi_14, sma_20, sma_50, sma_200, macd, bollinger_upper, volatility_20d, beta
print(technicals[['ticker', 'trade_date', 'rsi_14', 'volatility_20d']])
```

### 2. Equity Screening

```python
# Screen by technical indicators (NEW!)
oversold_tickers = equity.screen_by_technicals(
    rsi_max=30,           # RSI < 30 (oversold)
    volatility_max=0.02,  # Low volatility
    trade_date={'start': '2024-01-01'}
)
# Returns: ['AAPL', 'MSFT', ...]
```

### 3. Corporate Entity Data

```python
from models.implemented.corporate.model import CorporateModel

corporate = CorporateModel(connection, storage, repo)

# Get company information (NEW!)
companies = corporate.get_company_info(
    tickers=['AAPL', 'MSFT']
)

# Columns: company_id, company_name, sector, industry, headquarters_city
print(companies[['company_name', 'sector', 'industry']])
```

### 4. Cross-Model Queries (Future)

```python
# Once SEC data is integrated, you can join equity + corporate:

# Get undervalued stocks with good technicals
undervalued = corporate.screen_by_fundamentals(
    pe_max=15,
    roe_min=15
)

oversold = equity.screen_by_technicals(
    rsi_max=30
)

# Find intersection
opportunities = set(undervalued) & set(oversold)
```

---

## ⚠️ Breaking Changes

### 1. Table Names Changed

| Old | New | Notes |
|-----|-----|-------|
| `fact_prices` | `fact_equity_prices` | Legacy name still works via compatibility |
| `fact_news` | `fact_equity_news` | Legacy name still works |
| `dim_company` | `dim_equity` | Use equity model |
| N/A | `dim_corporate` | Use corporate model |

### 2. Storage Paths Changed

```
# OLD
storage/silver/company/
  ├── dims/dim_company/
  ├── facts/fact_prices/
  └── facts/fact_news/

# NEW
storage/silver/equity/
  ├── dims/dim_equity/
  ├── facts/fact_equity_prices/
  ├── facts/fact_equity_technicals/  ← NEW!
  └── facts/fact_equity_news/

storage/silver/corporate/  ← NEW!
  ├── dims/dim_corporate/
  ├── facts/fact_sec_filings/
  └── facts/fact_financials/
```

**Action:** Re-run data pipelines to populate new paths, or create symlinks for migration.

### 3. Config Files

```
# OLD
configs/models/company.yaml

# NEW
configs/models/equity.yaml    ← For price/trading data
configs/models/corporate.yaml ← For fundamentals (future)

# Legacy company.yaml still exists but is deprecated
```

---

## 🔧 Compatibility Layer

The `EquityModel` includes a compatibility layer for seamless migration:

```python
# In EquityModel.get_table():
table_mapping = {
    'fact_prices': 'fact_equity_prices',
    'fact_news': 'fact_equity_news',
    'prices_with_company': 'equity_prices_with_company',
    'news_with_company': 'equity_news_with_company',
    'dim_company': 'dim_equity',
}
```

**What this means:**
- Old table names automatically map to new names
- No immediate code changes required
- Gradual migration is supported

---

## 📝 Migration Checklist

### Phase 1: Update Imports (Low Risk)
- [ ] Replace `CompanyModel` with `EquityModel` in imports
- [ ] Test that existing code still works
- [ ] Verify measures calculate correctly

### Phase 2: Update Table Names (Medium Risk)
- [ ] Update `get_table()` calls to use new table names
- [ ] Update exhibit configs to reference `equity` model
- [ ] Test notebooks and scripts

### Phase 3: Update Data Pipelines (High Risk)
- [ ] Update bronze→silver transforms to use equity schema
- [ ] Re-run pipelines to populate new storage paths
- [ ] Verify data integrity

### Phase 4: Leverage New Features
- [ ] Add technical indicators to exhibits
- [ ] Create screening workflows
- [ ] Plan SEC EDGAR integration for corporate model

### Phase 5: Remove Legacy Code
- [ ] Remove `company.yaml` config (optional)
- [ ] Remove company model code (optional)
- [ ] Update documentation

---

## 🐛 Troubleshooting

### Issue: "Table not found: fact_equity_prices"

**Cause:** New equity model paths don't have data yet.

**Solution:**
```python
# Option 1: Re-run data pipeline
python scripts/run_equity_pipeline.py

# Option 2: Use legacy compatibility
equity = EquityModel(...)
prices = equity.get_table('fact_prices')  # Uses old path
```

### Issue: "Module not found: models.implemented.equity"

**Cause:** Equity model not imported in registry.

**Solution:**
```python
# models/registry.py
def _register_default_models(self):
    # Add equity model
    from models.implemented.equity.model import EquityModel
    self.register_model_class('equity', EquityModel)
```

### Issue: "Measure not found in equity model"

**Cause:** Measure name might have changed or not migrated.

**Solution:**
```python
# Check available measures
equity = EquityModel(...)
print(equity.model_cfg['measures'].keys())

# All company measures were migrated to equity
# Names are the same: avg_close_price, volume_weighted_index, etc.
```

### Issue: "Cross-model edge not working"

**Cause:** Corporate model not loaded or edge not defined.

**Solution:**
```yaml
# equity.yaml - ensure edge is defined
edges:
  - from: dim_equity.company_id
    to: corporate.dim_corporate.company_id
    type: many_to_one
```

---

## 📚 Examples

### Example 1: Basic Migration

**Before:**
```python
from models.implemented.company.model import CompanyModel

company = CompanyModel(connection, storage, repo)
result = company.calculate_measure_by_ticker('avg_close_price', limit=10)
print(result.data)
```

**After:**
```python
from models.implemented.equity.model import EquityModel

equity = EquityModel(connection, storage, repo)
result = equity.calculate_measure_by_ticker('avg_close_price', limit=10)
print(result.data)  # Same output!
```

### Example 2: Using Technical Indicators

```python
from models.implemented.equity.model import EquityModel

equity = EquityModel(connection, storage, repo)

# Get RSI for screening
oversold = equity.screen_by_technicals(
    rsi_max=30,
    trade_date={'start': '2024-01-01'}
)

print(f"Found {len(oversold)} oversold stocks: {oversold}")

# Get detailed technicals
technicals = equity.get_equity_technicals(
    tickers=oversold[:10],
    start_date='2024-01-01'
)

print(technicals[['ticker', 'trade_date', 'rsi_14', 'volatility_20d']])
```

### Example 3: Cross-Model Analysis (Future)

```python
from models.implemented.equity.model import EquityModel
from models.implemented.corporate.model import CorporateModel

# Initialize both models
equity = EquityModel(connection, storage, repo)
corporate = CorporateModel(connection, storage, repo)

# Screen by fundamentals
undervalued = corporate.screen_by_fundamentals(
    pe_max=15,
    roe_min=15
)

# Screen by technicals
oversold = equity.screen_by_technicals(
    rsi_max=30
)

# Find opportunities (intersection)
opportunities = set(undervalued) & set(oversold)
print(f"Found {len(opportunities)} opportunities: {opportunities}")

# Get detailed data for opportunities
for ticker in list(opportunities)[:5]:
    prices = equity.get_equity_prices(tickers=[ticker], limit=30)
    company_info = corporate.get_company_info(tickers=[ticker])
    print(f"\n{ticker}:")
    print(f"  Sector: {company_info['sector'].iloc[0]}")
    print(f"  Latest price: ${prices['close'].iloc[-1]:.2f}")
```

---

## 🚀 Benefits of Migration

### Conceptual Clarity
- ✅ Clear separation: Equity (trading) vs. Corporate (entity)
- ✅ Can model multi-class shares (GOOG/GOOGL)
- ✅ Foundation for SEC filings integration

### Code Organization
- ✅ Focused models with clear responsibilities
- ✅ Domain patterns organized by concern
- ✅ Easier to extend and maintain

### New Capabilities
- ✅ Technical indicators (RSI, MACD, Bollinger Bands)
- ✅ Risk metrics (beta, volatility, Sharpe ratio)
- ✅ Future: Fundamental analysis (P/E, ROE, growth rates)

### Performance
- ✅ Same unified measure framework
- ✅ Backend abstraction (DuckDB + Spark)
- ✅ On-demand calculations

---

## 📞 Support

**Questions?**
- See `docs/DOMAIN_ARCHITECTURE_PROPOSAL.md` for full architecture
- See `docs/IMPLEMENTATION_SUMMARY.md` for implementation details
- See `docs/TESTING_GUIDE.md` for testing strategies

**Migration Issues?**
- Check compatibility layer in `EquityModel.get_table()`
- Verify table names in `equity.yaml` config
- Review bronze source mappings

**Ready to migrate?** Start with Phase 1 (Update Imports) - it's low risk and backward compatible!
