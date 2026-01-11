---
type: api-endpoint
provider: Alpha Vantage
endpoint_id: company_overview

# API Configuration
endpoint_pattern: ""
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  function: OVERVIEW
required_params: [symbol]

# Pagination
pagination_type: none
bulk_download: false

# Metadata
domain: securities
legal_entity_type: vendor
subject_entity_tags: [corporate]
data_tags: [reference, fundamentals]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "One API call per ticker - no bulk endpoint"

# Bronze Layer Configuration
bronze:
  table: company_reference
  partitions: []
  write_strategy: upsert
  key_columns: [cik]
  date_column: null
  comment: "Company fundamentals from OVERVIEW - CIK as primary key for SEC linkage"
---

## Description

Company overview including sector, industry, market cap, PE ratio, and other fundamentals. The OVERVIEW endpoint provides comprehensive company data including the SEC CIK (Central Index Key) which enables linkage to SEC EDGAR filings.

This is the primary source for the `company` Silver model's `dim_company` dimension.

## Schema

```yaml
# Format: [field_name, type, source_field, nullable, description]
schema:
  - [ticker, string, Symbol, false, "Stock ticker symbol"]
  - [cik, string, CIK, true, "SEC Central Index Key (10 digits, zero-padded)"]
  - [company_name, string, Name, true, "Company legal name"]
  - [sector, string, Sector, true, "GICS Sector"]
  - [industry, string, Industry, true, "GICS Industry"]
  - [description, string, Description, true, "Business description"]
  - [exchange_code, string, Exchange, true, "Primary exchange (NYSE, NASDAQ)"]
  - [country, string, Country, true, "Country of incorporation"]
  - [currency, string, Currency, true, "Reporting currency"]
  - [fiscal_year_end, string, FiscalYearEnd, true, "Fiscal year end month"]
  - [shares_outstanding, long, SharesOutstanding, true, "Total shares outstanding"]
  - [market_cap, double, MarketCapitalization, true, "Market capitalization USD"]
  - [pe_ratio, double, PERatio, true, "Price to earnings ratio"]
  - [peg_ratio, double, PEGRatio, true, "Price/earnings to growth ratio"]
  - [book_value, double, BookValue, true, "Book value per share"]
  - [dividend_per_share, double, DividendPerShare, true, "Annual dividend per share"]
  - [dividend_yield, double, DividendYield, true, "Dividend yield percentage"]
  - [eps, double, EPS, true, "Earnings per share (TTM)"]
  - [ebitda, double, EBITDA, true, "EBITDA"]
  - [revenue_ttm, double, RevenueTTM, true, "Trailing 12 month revenue"]
  - [profit_margin, double, ProfitMargin, true, "Profit margin percentage"]
  - [is_active, boolean, _generated, false, "Currently active (always true from API)"]
```

## Request Notes

- **One call per ticker**: No bulk endpoint available
- **Rate limit aware**: Respect 5 calls/min (free) or 75 calls/min (premium)
- **CIK Padding**: CIK should be zero-padded to 10 digits per SEC standard
- **Error detection**: Check for `"Error Message"` key in response

## Homelab Usage

```bash
# Ingest company data for specific tickers
python -m scripts.ingest.run_bronze_ingestion --endpoints company_overview --tickers AAPL MSFT GOOGL
```

## Known Quirks

1. **Numeric strings**: All numeric fields returned as strings, including `"None"` for nulls
2. **Non-US gaps**: Non-US tickers often missing OVERVIEW data entirely
3. **AssetType values**: Returns "Common Stock", "ETF", "Mutual Fund" (map to asset_type)
4. **CIK missing**: Some smaller companies lack CIK even when US-listed
5. **Data freshness**: Fundamentals may lag current quarter by weeks
