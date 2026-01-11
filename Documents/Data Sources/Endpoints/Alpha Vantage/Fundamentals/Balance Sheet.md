---
type: api-endpoint
provider: Alpha Vantage
endpoint_id: balance_sheet

# API Configuration
endpoint_pattern: ""
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  function: BALANCE_SHEET
required_params: [symbol]

# Pagination
pagination_type: none
bulk_download: false

# Metadata
domain: finance
legal_entity_type: vendor
subject_entity_tags: [corporate]
data_tags: [fundamentals, financial-statements, quarterly, annual]
status: active
update_cadence: quarterly
last_verified:
last_reviewed:
notes: "Returns both annualReports and quarterlyReports arrays"

# Bronze Layer Configuration
bronze:
  table: balance_sheets
  partitions: [report_type]
  write_strategy: upsert
  key_columns: [ticker, fiscal_date_ending, report_type]
  date_column: fiscal_date_ending
  comment: "Balance sheets - partitioned by annual/quarterly"
---

## Description

Annual and quarterly balance sheet data including assets, liabilities, and shareholder equity. Returns both `annualReports` and `quarterlyReports` arrays.

## Schema

```yaml
# Format: [field_name, type, source_field, nullable, description]
schema:
  - [ticker, string, symbol, false, "Stock ticker"]
  - [fiscal_date_ending, date, fiscalDateEnding, false, "End of fiscal period"]
  - [report_type, string, _generated, false, "annual or quarterly"]
  - [reported_currency, string, reportedCurrency, true, "Reporting currency"]
  - [total_assets, long, totalAssets, true, "Total assets"]
  - [total_current_assets, long, totalCurrentAssets, true, "Current assets"]
  - [cash_and_equivalents, long, cashAndCashEquivalentsAtCarryingValue, true, "Cash"]
  - [inventory, long, inventory, true, "Inventory"]
  - [current_net_receivables, long, currentNetReceivables, true, "Receivables"]
  - [total_non_current_assets, long, totalNonCurrentAssets, true, "Non-current assets"]
  - [property_plant_equipment, long, propertyPlantEquipment, true, "PP&E"]
  - [goodwill, long, goodwill, true, "Goodwill"]
  - [intangible_assets, long, intangibleAssets, true, "Intangibles"]
  - [total_liabilities, long, totalLiabilities, true, "Total liabilities"]
  - [total_current_liabilities, long, totalCurrentLiabilities, true, "Current liabilities"]
  - [accounts_payable, long, currentAccountsPayable, true, "Accounts payable"]
  - [short_term_debt, long, shortTermDebt, true, "Short-term debt"]
  - [long_term_debt, long, longTermDebt, true, "Long-term debt"]
  - [total_shareholder_equity, long, totalShareholderEquity, true, "Shareholder equity"]
  - [retained_earnings, long, retainedEarnings, true, "Retained earnings"]
  - [common_stock, long, commonStock, true, "Common stock"]
  - [shares_outstanding, long, commonStockSharesOutstanding, true, "Shares outstanding"]
```

## Request Notes

- All balance sheet items as of fiscal period end date
- Values in reporting currency (usually USD)

## Homelab Usage

```bash
python -m scripts.ingest.run_bronze_ingestion --endpoints balance_sheet --tickers AAPL MSFT
```

## Known Quirks

1. **String numerics**: All values as strings including "None"
2. **Field naming**: Some fields use camelCase with inconsistent patterns
3. **Missing fields**: Banks/financials have different field sets
