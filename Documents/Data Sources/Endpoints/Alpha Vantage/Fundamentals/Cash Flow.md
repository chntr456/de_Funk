---
type: api-endpoint
provider: Alpha Vantage
endpoint_id: cash_flow

# API Configuration
endpoint_pattern: ""
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  function: CASH_FLOW
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
  table: cash_flows
  partitions: [report_type]
  write_strategy: upsert
  key_columns: [ticker, fiscal_date_ending, report_type]
  date_column: fiscal_date_ending
  comment: "Cash flow statements - partitioned by annual/quarterly"
---

## Description

Annual and quarterly cash flow statement data including operating, investing, and financing activities. Returns both `annualReports` and `quarterlyReports` arrays.

## Schema

```yaml
# Format: [field_name, type, source_field, nullable, description]
schema:
  - [ticker, string, symbol, false, "Stock ticker"]
  - [fiscal_date_ending, date, fiscalDateEnding, false, "End of fiscal period"]
  - [report_type, string, _generated, false, "annual or quarterly"]
  - [reported_currency, string, reportedCurrency, true, "Reporting currency"]
  - [operating_cashflow, long, operatingCashflow, true, "Cash from operations"]
  - [payments_for_operating_activities, long, paymentsForOperatingActivities, true, "Operating payments"]
  - [change_in_operating_liabilities, long, changeInOperatingLiabilities, true, "Change in op liabilities"]
  - [change_in_operating_assets, long, changeInOperatingAssets, true, "Change in op assets"]
  - [depreciation_depletion_amortization, long, depreciationDepletionAndAmortization, true, "D&A"]
  - [capital_expenditures, long, capitalExpenditures, true, "CapEx"]
  - [change_in_receivables, long, changeInReceivables, true, "Change in receivables"]
  - [change_in_inventory, long, changeInInventory, true, "Change in inventory"]
  - [profit_loss, long, profitLoss, true, "Net profit/loss"]
  - [cashflow_from_investment, long, cashflowFromInvestment, true, "Cash from investing"]
  - [cashflow_from_financing, long, cashflowFromFinancing, true, "Cash from financing"]
  - [dividend_payout, long, dividendPayout, true, "Dividends paid"]
  - [dividend_payout_common, long, dividendPayoutCommonStock, true, "Common dividends"]
  - [dividend_payout_preferred, long, dividendPayoutPreferredStock, true, "Preferred dividends"]
  - [proceeds_from_stock_issuance, long, proceedsFromIssuanceOfCommonStock, true, "Stock issuance proceeds"]
  - [proceeds_from_stock_repurchase, long, paymentsForRepurchaseOfCommonStock, true, "Buyback payments"]
  - [net_change_in_cash, long, changeInCashAndCashEquivalents, true, "Net change in cash"]
```

## Request Notes

- Operating, investing, financing sections each contain multiple line items
- Negative values indicate cash outflows

## Homelab Usage

```bash
python -m scripts.ingest.run_bronze_ingestion --endpoints cash_flow --tickers AAPL MSFT
```

## Known Quirks

1. **String numerics**: All values as strings including "None"
2. **Sign convention**: CapEx typically negative, dividends negative
3. **Historical depth**: ~5 years annual, ~5 years quarterly
