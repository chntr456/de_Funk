# Proposal: Alpha Vantage Pipeline Expansion & Unified Cashflow Model

**Status**: Partially Accepted
**Author**: Claude
**Date**: 2025-11-30
**Updated**: 2025-12-02
**Priority**: High

## Implementation Notes (2025-12-02)

Part 1 (Alpha Vantage Pipeline Expansion) has been implemented:
- Added endpoints to `configs/alpha_vantage_endpoints.json` for income_statement, balance_sheet, cash_flow, earnings, historical_options, etf_profile, earnings_calendar, realtime_options, top_gainers_losers
- Created facets in `datapipelines/providers/alpha_vantage/facets/`:
  - `income_statement_facet.py`
  - `balance_sheet_facet.py`
  - `cash_flow_facet.py`
  - `earnings_facet.py`
  - `historical_options_facet.py`
- Added ingestion methods to `AlphaVantageIngestor`:
  - `ingest_income_statements()`
  - `ingest_balance_sheets()`
  - `ingest_cash_flows()`
  - `ingest_earnings()`
  - `ingest_historical_options()`
  - `ingest_fundamentals()` - convenience method for all fundamentals
  - `run_comprehensive()` - extended pipeline with fundamentals and options

Part 2 (Unified Cashflow Model) is deferred to future work.

---

## Summary

This proposal covers two interconnected initiatives:

1. **Alpha Vantage Pipeline Expansion**: Add data pipelines for options, ETFs, and company fundamentals (income statement, balance sheet, cash flow)
2. **Unified Cashflow Model**: Create a common abstraction for financial statements that works across both municipal (city finance) and corporate entities

The unified cashflow model recognizes that both municipal budgets and corporate financials track money flows through an organization - just with different account structures.

---

## Part 1: Alpha Vantage Pipeline Expansion

### Current State

The existing Alpha Vantage configuration (`configs/alpha_vantage_endpoints.json`) supports:
- `company_overview` - Basic company fundamentals
- `time_series_daily` / `time_series_daily_adjusted` - Price history
- `global_quote` - Realtime quotes
- `listing_status` - Active/delisted tickers
- `symbol_search` - Ticker lookup
- Technical indicators (SMA, RSI, MACD)

### Missing Endpoints

| Category | Endpoint | Alpha Vantage Function | Priority |
|----------|----------|----------------------|----------|
| **Fundamentals** | Income Statement | `INCOME_STATEMENT` | High |
| **Fundamentals** | Balance Sheet | `BALANCE_SHEET` | High |
| **Fundamentals** | Cash Flow | `CASH_FLOW` | High |
| **Fundamentals** | Earnings | `EARNINGS` | Medium |
| **Fundamentals** | Earnings Calendar | `EARNINGS_CALENDAR` | Medium |
| **Options** | Historical Options | `HISTORICAL_OPTIONS` | High |
| **ETFs** | ETF Profile | `ETF_PROFILE` | Medium |

### Endpoint Configuration

**Add to `configs/alpha_vantage_endpoints.json`**:

```json
{
  "income_statement": {
    "base": "core",
    "method": "GET",
    "path_template": "",
    "required_params": ["symbol"],
    "default_query": {
      "function": "INCOME_STATEMENT"
    },
    "response_key": null,
    "comment": "Annual and quarterly income statements. Returns annualReports and quarterlyReports arrays."
  },
  "balance_sheet": {
    "base": "core",
    "method": "GET",
    "path_template": "",
    "required_params": ["symbol"],
    "default_query": {
      "function": "BALANCE_SHEET"
    },
    "response_key": null,
    "comment": "Annual and quarterly balance sheets with GAAP/IFRS normalized fields."
  },
  "cash_flow": {
    "base": "core",
    "method": "GET",
    "path_template": "",
    "required_params": ["symbol"],
    "default_query": {
      "function": "CASH_FLOW"
    },
    "response_key": null,
    "comment": "Annual and quarterly cash flow statements."
  },
  "earnings": {
    "base": "core",
    "method": "GET",
    "path_template": "",
    "required_params": ["symbol"],
    "default_query": {
      "function": "EARNINGS"
    },
    "response_key": null,
    "comment": "Annual and quarterly earnings (EPS actual vs estimate)."
  },
  "historical_options": {
    "base": "core",
    "method": "GET",
    "path_template": "",
    "required_params": ["symbol"],
    "default_query": {
      "function": "HISTORICAL_OPTIONS"
    },
    "response_key": "data",
    "comment": "Historical options chain data including strike, expiry, Greeks. Premium endpoint."
  },
  "etf_profile": {
    "base": "core",
    "method": "GET",
    "path_template": "",
    "required_params": ["symbol"],
    "default_query": {
      "function": "ETF_PROFILE"
    },
    "response_key": null,
    "comment": "ETF profile including holdings, sector weights, expense ratio."
  }
}
```

### New Facets Required

| Facet | Purpose | Output Table |
|-------|---------|--------------|
| `IncomeStatementFacet` | Normalize income statement JSON | `bronze.company_income_statement` |
| `BalanceSheetFacet` | Normalize balance sheet JSON | `bronze.company_balance_sheet` |
| `CashFlowFacet` | Normalize cash flow JSON | `bronze.company_cash_flow` |
| `EarningsFacet` | Normalize earnings data | `bronze.company_earnings` |
| `HistoricalOptionsFacet` | Normalize options chain | `bronze.options_historical` |
| `ETFProfileFacet` | Normalize ETF profile | `bronze.etf_profile` |

### Facet Implementation Pattern

**File**: `datapipelines/facets/alpha_vantage/income_statement_facet.py`

```python
"""
Income Statement Facet.

Transforms Alpha Vantage INCOME_STATEMENT response into normalized schema.
"""

from typing import Dict, Any, List
from datetime import datetime
import pandas as pd

from datapipelines.base.facet import BaseFacet
from config.logging import get_logger

logger = get_logger(__name__)


class IncomeStatementFacet(BaseFacet):
    """Transform income statement API response to normalized DataFrame."""

    def __init__(self):
        super().__init__(
            facet_name="income_statement",
            output_table="company_income_statement"
        )

    def transform(self, raw_data: Dict[str, Any], ticker: str) -> pd.DataFrame:
        """
        Transform income statement response.

        Args:
            raw_data: API response with annualReports and quarterlyReports
            ticker: Stock ticker symbol

        Returns:
            Normalized DataFrame with all periods
        """
        records = []

        # Process annual reports
        for report in raw_data.get("annualReports", []):
            records.append(self._normalize_report(report, ticker, "annual"))

        # Process quarterly reports
        for report in raw_data.get("quarterlyReports", []):
            records.append(self._normalize_report(report, ticker, "quarterly"))

        if not records:
            logger.warning(f"No income statement data for {ticker}")
            return pd.DataFrame()

        return pd.DataFrame(records)

    def _normalize_report(
        self,
        report: Dict[str, Any],
        ticker: str,
        period_type: str
    ) -> Dict[str, Any]:
        """Normalize a single report to standard schema."""
        return {
            "ticker": ticker,
            "fiscal_date_ending": report.get("fiscalDateEnding"),
            "period_type": period_type,
            "reported_currency": report.get("reportedCurrency"),

            # Revenue
            "total_revenue": self._safe_float(report.get("totalRevenue")),
            "cost_of_revenue": self._safe_float(report.get("costOfRevenue")),
            "gross_profit": self._safe_float(report.get("grossProfit")),

            # Operating
            "operating_expenses": self._safe_float(report.get("operatingExpenses")),
            "operating_income": self._safe_float(report.get("operatingIncome")),

            # Other Income/Expense
            "interest_expense": self._safe_float(report.get("interestExpense")),
            "interest_income": self._safe_float(report.get("interestIncome")),

            # Taxes & Net
            "income_before_tax": self._safe_float(report.get("incomeBeforeTax")),
            "income_tax_expense": self._safe_float(report.get("incomeTaxExpense")),
            "net_income": self._safe_float(report.get("netIncome")),

            # Per Share
            "ebitda": self._safe_float(report.get("ebitda")),

            # Metadata
            "ingested_at": datetime.utcnow(),
        }

    def _safe_float(self, value: Any) -> float:
        """Safely convert to float, returning None for 'None' strings."""
        if value is None or value == "None":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
```

---

## Part 2: Unified Cashflow Model

### Motivation

Both municipal finance and corporate finance track the same fundamental concept: **money flowing through an organization**. The difference is terminology and account structure:

| Concept | Municipal Finance | Corporate Finance |
|---------|------------------|-------------------|
| **Entity** | City, Department, Fund | Company, Business Unit |
| **Inflows** | Revenues, Taxes, Grants | Revenue, Other Income |
| **Outflows** | Expenditures, Transfers | Expenses, COGS |
| **Categories** | Fund, Department, Account | Statement Type, Category, Line Item |
| **Periods** | Fiscal Year, Quarter | Fiscal Year, Quarter |

### Unified Abstraction

Create a **chart of accounts** abstraction that normalizes both:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    UNIFIED CASHFLOW MODEL                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  dim_entity              dim_account              dim_account_type  │
│  ├── entity_id           ├── account_id          ├── type_id       │
│  ├── entity_type         ├── account_code        ├── type_name     │
│  │   (city/company)      ├── account_name        ├── flow_direction│
│  ├── entity_name         ├── parent_account_id   │   (inflow/      │
│  └── sector/department   ├── account_level       │    outflow)     │
│                          └── statement_type      └── is_operating  │
│                              (income/balance/                       │
│                               cashflow/budget)                      │
│                                                                     │
│  fact_cashflow                                                      │
│  ├── entity_id (FK)                                                 │
│  ├── account_id (FK)                                                │
│  ├── period_date                                                    │
│  ├── period_type (annual/quarterly/monthly)                         │
│  ├── amount                                                         │
│  ├── amount_budget (for municipal)                                  │
│  ├── amount_prior_period                                            │
│  └── currency                                                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Schema Definition

**File**: `configs/models/cashflow/schema.yaml`

```yaml
model: cashflow
version: 2.0
description: "Unified cashflow model for municipal and corporate financial statements"

metadata:
  owner: "finance_team"
  domain: "finance"
  tags: [finance, cashflow, municipal, corporate, unified]

depends_on:
  - core
  - company
  - city_finance

schema:
  dimensions:
    # ========================================
    # Entity Dimension (City or Company)
    # ========================================
    dim_entity:
      description: "Reporting entities (cities, companies, departments)"
      columns:
        entity_id:
          type: string
          description: "PK - Unique entity identifier"
          required: true

        entity_type:
          type: string
          description: "Type: 'municipal', 'corporate', 'department', 'fund'"
          required: true

        entity_name:
          type: string
          description: "Entity name"
          required: true

        parent_entity_id:
          type: string
          description: "Parent entity for hierarchies (e.g., department -> city)"

        # For municipal
        jurisdiction:
          type: string
          description: "City, county, state for municipal entities"

        fund_type:
          type: string
          description: "General, Special Revenue, Enterprise, etc."

        # For corporate
        cik:
          type: string
          description: "SEC CIK for companies"

        sector:
          type: string
          description: "Industry sector for companies"

        ticker:
          type: string
          description: "Primary ticker for companies"

        fiscal_year_end:
          type: string
          description: "Fiscal year end (MM-DD)"

      primary_key: [entity_id]
      tags: [dim, entity, unified]

    # ========================================
    # Account Dimension (Chart of Accounts)
    # ========================================
    dim_account:
      description: "Unified chart of accounts across entity types"
      columns:
        account_id:
          type: string
          description: "PK - Unique account identifier"
          required: true

        account_code:
          type: string
          description: "Account code (e.g., '4100' for revenue)"

        account_name:
          type: string
          description: "Account name"
          required: true

        account_type_id:
          type: string
          description: "FK to dim_account_type"

        parent_account_id:
          type: string
          description: "Parent account for hierarchy"

        account_level:
          type: int
          description: "Hierarchy level (1=top, 2=category, 3=detail)"

        statement_type:
          type: string
          description: "income_statement, balance_sheet, cash_flow, budget"

        # Mapping fields
        gaap_taxonomy:
          type: string
          description: "GAAP taxonomy mapping for corporate"

        gasb_taxonomy:
          type: string
          description: "GASB taxonomy mapping for municipal"

        is_calculated:
          type: boolean
          description: "True if derived from other accounts"
          default: false

      primary_key: [account_id]
      tags: [dim, account, chart_of_accounts]

    # ========================================
    # Account Type Dimension
    # ========================================
    dim_account_type:
      description: "Account classification types"
      columns:
        type_id:
          type: string
          required: true

        type_name:
          type: string
          description: "Asset, Liability, Equity, Revenue, Expense, etc."

        flow_direction:
          type: string
          description: "inflow, outflow, or balance"

        is_operating:
          type: boolean
          description: "Operating vs non-operating"

        normal_balance:
          type: string
          description: "debit or credit"

      primary_key: [type_id]
      tags: [dim, reference, accounting]

  facts:
    # ========================================
    # Unified Cashflow Fact
    # ========================================
    fact_cashflow:
      description: "Unified financial transactions and balances"
      columns:
        cashflow_id:
          type: string
          required: true

        entity_id:
          type: string
          description: "FK to dim_entity"
          required: true

        account_id:
          type: string
          description: "FK to dim_account"
          required: true

        period_date:
          type: date
          description: "Period end date"
          required: true

        period_type:
          type: string
          description: "annual, quarterly, monthly"
          required: true

        fiscal_year:
          type: int
          description: "Fiscal year"

        fiscal_period:
          type: int
          description: "Quarter (1-4) or month (1-12)"

        # Amounts
        amount:
          type: double
          description: "Actual/reported amount"

        amount_budget:
          type: double
          description: "Budgeted amount (municipal)"

        amount_prior_period:
          type: double
          description: "Prior period for comparison"

        amount_ytd:
          type: double
          description: "Year-to-date amount"

        # Metadata
        currency:
          type: string
          description: "Currency code (USD)"
          default: "USD"

        source_system:
          type: string
          description: "alpha_vantage, chicago_data, sec_edgar"

        reported_date:
          type: date
          description: "Date the data was reported/filed"

      primary_key: [cashflow_id]
      partitions: [period_date]
      tags: [fact, cashflow, unified]

    # ========================================
    # Budget vs Actual (Municipal Focus)
    # ========================================
    fact_budget_variance:
      description: "Budget to actual variance analysis"
      columns:
        variance_id:
          type: string
          required: true

        entity_id:
          type: string
          required: true

        account_id:
          type: string
          required: true

        period_date:
          type: date
          required: true

        budget_amount:
          type: double

        actual_amount:
          type: double

        variance_amount:
          type: double
          description: "actual - budget"

        variance_pct:
          type: double
          description: "(actual - budget) / budget"

        variance_status:
          type: string
          description: "favorable, unfavorable, on_target"

      primary_key: [variance_id]
      partitions: [period_date]
      tags: [fact, budget, variance, municipal]
```

### Standard Chart of Accounts Mapping

**File**: `configs/models/cashflow/seed/standard_accounts.yaml`

```yaml
# Standard account mappings for unified cashflow model
# Maps between corporate (GAAP) and municipal (GASB) taxonomies

account_types:
  - type_id: ASSET
    type_name: Asset
    flow_direction: balance
    is_operating: false
    normal_balance: debit

  - type_id: LIABILITY
    type_name: Liability
    flow_direction: balance
    is_operating: false
    normal_balance: credit

  - type_id: EQUITY
    type_name: Equity
    flow_direction: balance
    is_operating: false
    normal_balance: credit

  - type_id: REVENUE
    type_name: Revenue
    flow_direction: inflow
    is_operating: true
    normal_balance: credit

  - type_id: EXPENSE
    type_name: Expense
    flow_direction: outflow
    is_operating: true
    normal_balance: debit

  - type_id: OPERATING_CF
    type_name: Operating Cash Flow
    flow_direction: inflow
    is_operating: true
    normal_balance: debit

  - type_id: INVESTING_CF
    type_name: Investing Cash Flow
    flow_direction: outflow
    is_operating: false
    normal_balance: debit

  - type_id: FINANCING_CF
    type_name: Financing Cash Flow
    flow_direction: inflow
    is_operating: false
    normal_balance: debit

# Unified accounts with mappings
accounts:
  # ========================================
  # REVENUE / INFLOWS
  # ========================================
  - account_id: REV_TOTAL
    account_code: "4000"
    account_name: Total Revenue
    account_type_id: REVENUE
    account_level: 1
    statement_type: income_statement
    gaap_taxonomy: us-gaap:Revenues
    gasb_taxonomy: gasb:TotalRevenues

  - account_id: REV_OPERATING
    account_code: "4100"
    account_name: Operating Revenue
    parent_account_id: REV_TOTAL
    account_type_id: REVENUE
    account_level: 2
    statement_type: income_statement
    gaap_taxonomy: us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax
    gasb_taxonomy: gasb:ChargesForServices

  - account_id: REV_TAXES
    account_code: "4200"
    account_name: Tax Revenue
    parent_account_id: REV_TOTAL
    account_type_id: REVENUE
    account_level: 2
    statement_type: income_statement
    gaap_taxonomy: null  # Corporate doesn't have tax revenue
    gasb_taxonomy: gasb:Taxes

  - account_id: REV_GRANTS
    account_code: "4300"
    account_name: Grants and Contributions
    parent_account_id: REV_TOTAL
    account_type_id: REVENUE
    account_level: 2
    statement_type: income_statement
    gaap_taxonomy: us-gaap:GrantIncome
    gasb_taxonomy: gasb:GrantsAndContributionsNotRestrictedToSpecificPrograms

  # ========================================
  # EXPENSES / OUTFLOWS
  # ========================================
  - account_id: EXP_TOTAL
    account_code: "5000"
    account_name: Total Expenses
    account_type_id: EXPENSE
    account_level: 1
    statement_type: income_statement
    gaap_taxonomy: us-gaap:CostsAndExpenses
    gasb_taxonomy: gasb:TotalExpenditures

  - account_id: EXP_PERSONNEL
    account_code: "5100"
    account_name: Personnel / Compensation
    parent_account_id: EXP_TOTAL
    account_type_id: EXPENSE
    account_level: 2
    statement_type: income_statement
    gaap_taxonomy: us-gaap:LaborAndRelatedExpense
    gasb_taxonomy: gasb:PersonnelServices

  - account_id: EXP_OPERATIONS
    account_code: "5200"
    account_name: Operating Expenses
    parent_account_id: EXP_TOTAL
    account_type_id: EXPENSE
    account_level: 2
    statement_type: income_statement
    gaap_taxonomy: us-gaap:OperatingExpenses
    gasb_taxonomy: gasb:OperatingExpenditures

  - account_id: EXP_CAPITAL
    account_code: "5300"
    account_name: Capital Expenditures
    parent_account_id: EXP_TOTAL
    account_type_id: EXPENSE
    account_level: 2
    statement_type: income_statement
    gaap_taxonomy: us-gaap:PaymentsToAcquirePropertyPlantAndEquipment
    gasb_taxonomy: gasb:CapitalOutlay

  - account_id: EXP_DEBT_SERVICE
    account_code: "5400"
    account_name: Debt Service
    parent_account_id: EXP_TOTAL
    account_type_id: EXPENSE
    account_level: 2
    statement_type: income_statement
    gaap_taxonomy: us-gaap:InterestExpense
    gasb_taxonomy: gasb:DebtService

  # ========================================
  # CASH FLOW - OPERATING
  # ========================================
  - account_id: CF_OPERATING
    account_code: "7000"
    account_name: Cash from Operations
    account_type_id: OPERATING_CF
    account_level: 1
    statement_type: cash_flow
    gaap_taxonomy: us-gaap:NetCashProvidedByUsedInOperatingActivities
    gasb_taxonomy: gasb:CashFlowsFromOperatingActivities

  - account_id: CF_INVESTING
    account_code: "7100"
    account_name: Cash from Investing
    account_type_id: INVESTING_CF
    account_level: 1
    statement_type: cash_flow
    gaap_taxonomy: us-gaap:NetCashProvidedByUsedInInvestingActivities
    gasb_taxonomy: gasb:CashFlowsFromCapitalAndRelatedFinancingActivities

  - account_id: CF_FINANCING
    account_code: "7200"
    account_name: Cash from Financing
    account_type_id: FINANCING_CF
    account_level: 1
    statement_type: cash_flow
    gaap_taxonomy: us-gaap:NetCashProvidedByUsedInFinancingActivities
    gasb_taxonomy: gasb:CashFlowsFromNoncapitalFinancingActivities
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     DATA SOURCES                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Alpha Vantage                     Chicago Data Portal              │
│  ├── INCOME_STATEMENT              ├── Budget Appropriations        │
│  ├── BALANCE_SHEET                 ├── Annual Financial Report      │
│  ├── CASH_FLOW                     └── Department Expenditures      │
│  └── EARNINGS                                                       │
│                                                                     │
└───────────────┬─────────────────────────────┬───────────────────────┘
                │                             │
                ▼                             ▼
┌───────────────────────────────┐ ┌───────────────────────────────────┐
│      BRONZE LAYER             │ │        BRONZE LAYER               │
│  company_income_statement     │ │   chicago_budget                  │
│  company_balance_sheet        │ │   chicago_expenditures            │
│  company_cash_flow            │ │                                   │
└───────────────┬───────────────┘ └───────────────┬───────────────────┘
                │                                 │
                └────────────────┬────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────────┐
                    │   CASHFLOW MODEL (Silver)  │
                    │  ├── dim_entity            │
                    │  ├── dim_account           │
                    │  ├── dim_account_type      │
                    │  ├── fact_cashflow         │
                    │  └── fact_budget_variance  │
                    └────────────────────────────┘
```

### Transformation Logic

**File**: `models/implemented/cashflow/transforms/corporate_loader.py`

```python
"""
Corporate Financial Statement Loader.

Transforms Alpha Vantage financial statements into unified cashflow model.
Uses Spark for batch processing (pre-calculation task).
"""

from typing import Dict, List
from datetime import datetime
import pandas as pd

from core.session.universal_session import UniversalSession
from config.logging import get_logger

logger = get_logger(__name__)


class CorporateFinancialLoader:
    """Load corporate financials into unified cashflow model."""

    # Mapping from Alpha Vantage fields to unified accounts
    INCOME_STATEMENT_MAPPING = {
        "totalRevenue": "REV_TOTAL",
        "costOfRevenue": "EXP_COGS",
        "grossProfit": "REV_GROSS_PROFIT",
        "operatingExpenses": "EXP_OPERATIONS",
        "operatingIncome": "REV_OPERATING_INCOME",
        "interestExpense": "EXP_INTEREST",
        "incomeBeforeTax": "REV_PRETAX",
        "incomeTaxExpense": "EXP_TAX",
        "netIncome": "REV_NET_INCOME",
    }

    CASH_FLOW_MAPPING = {
        "operatingCashflow": "CF_OPERATING",
        "cashflowFromInvestment": "CF_INVESTING",
        "cashflowFromFinancing": "CF_FINANCING",
        "capitalExpenditures": "EXP_CAPITAL",
    }

    def __init__(self, backend: str = "spark"):
        """Initialize with Spark backend for batch processing."""
        self.session = UniversalSession(backend=backend)

    def load_company_financials(
        self,
        ticker: str,
        cik: str,
        income_statement: pd.DataFrame,
        cash_flow: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Transform company financial statements to unified format.

        Args:
            ticker: Stock ticker
            cik: SEC CIK
            income_statement: Raw income statement data
            cash_flow: Raw cash flow data

        Returns:
            DataFrame in fact_cashflow format
        """
        entity_id = f"COMPANY_{cik}"
        records = []

        # Process income statement
        for _, row in income_statement.iterrows():
            period_date = row.get("fiscal_date_ending")
            period_type = row.get("period_type", "annual")

            for field, account_id in self.INCOME_STATEMENT_MAPPING.items():
                amount = row.get(field)
                if amount is not None:
                    records.append({
                        "cashflow_id": f"{entity_id}_{account_id}_{period_date}",
                        "entity_id": entity_id,
                        "account_id": account_id,
                        "period_date": period_date,
                        "period_type": period_type,
                        "amount": float(amount),
                        "currency": row.get("reported_currency", "USD"),
                        "source_system": "alpha_vantage",
                        "reported_date": datetime.utcnow().date(),
                    })

        # Process cash flow
        for _, row in cash_flow.iterrows():
            period_date = row.get("fiscal_date_ending")
            period_type = row.get("period_type", "annual")

            for field, account_id in self.CASH_FLOW_MAPPING.items():
                amount = row.get(field)
                if amount is not None:
                    records.append({
                        "cashflow_id": f"{entity_id}_{account_id}_{period_date}",
                        "entity_id": entity_id,
                        "account_id": account_id,
                        "period_date": period_date,
                        "period_type": period_type,
                        "amount": float(amount),
                        "currency": row.get("reported_currency", "USD"),
                        "source_system": "alpha_vantage",
                        "reported_date": datetime.utcnow().date(),
                    })

        return pd.DataFrame(records)
```

---

## Part 3: Options & ETF Model Updates

### Options Model Enhancement

Update `configs/models/options/` to consume historical options data:

```yaml
# configs/models/options/schema.yaml (additions)
facts:
  fact_options_chain:
    description: "Historical options chain data"
    columns:
      chain_id: string
      underlying_ticker: string
      option_type: string  # call, put
      strike_price: double
      expiration_date: date
      trade_date: date

      # Prices
      bid: double
      ask: double
      last_price: double
      volume: long
      open_interest: long

      # Greeks (if available)
      delta: double
      gamma: double
      theta: double
      vega: double
      implied_volatility: double

    partitions: [trade_date]
    tags: [fact, options, greeks]
```

### ETF Model Enhancement

Update `configs/models/etf/` to include profile data:

```yaml
# configs/models/etf/schema.yaml (additions)
dimensions:
  dim_etf:
    description: "ETF master with profile data"
    columns:
      etf_id: string
      ticker: string
      fund_name: string
      issuer: string
      expense_ratio: double
      inception_date: date
      aum: double  # Assets Under Management
      nav: double  # Net Asset Value

      # Classification
      asset_class: string
      category: string
      focus: string
      niche: string

      # Holdings
      holdings_count: int
      top_10_weight_pct: double

    primary_key: [ticker]
    tags: [dim, etf, profile]

  dim_etf_holdings:
    description: "ETF constituent holdings"
    columns:
      holding_id: string
      etf_ticker: string
      holding_ticker: string
      holding_name: string
      weight_pct: double
      shares: long
      market_value: double
      sector: string
      as_of_date: date

    primary_key: [etf_ticker, holding_ticker, as_of_date]
    tags: [dim, etf, holdings]
```

---

## Implementation Plan

### Phase 1: Alpha Vantage Endpoints (Week 1)
1. Add new endpoints to `alpha_vantage_endpoints.json`
2. Implement facets for income statement, balance sheet, cash flow
3. Test with sample tickers
4. Add to ingestion pipeline

### Phase 2: Unified Cashflow Schema (Week 2)
1. Create `configs/models/cashflow/` directory structure
2. Define schema.yaml with dimensions and facts
3. Create standard accounts seed data
4. Implement entity and account loaders

### Phase 3: Corporate Loader (Week 3)
1. Implement `CorporateFinancialLoader`
2. Map Alpha Vantage fields to unified accounts
3. Build and test with sample companies
4. Verify data in DuckDB

### Phase 4: Municipal Integration (Week 4)
1. Add Chicago budget/expenditure endpoints
2. Implement `MunicipalFinancialLoader`
3. Map Chicago accounts to unified structure
4. Create budget variance fact

### Phase 5: Options & ETF (Week 5)
1. Add historical options endpoint and facet
2. Add ETF profile endpoint and facet
3. Update options and ETF model schemas
4. Build and test

---

## Cross-Model Queries

Once implemented, enable queries like:

```sql
-- Compare corporate vs municipal revenue growth
SELECT
    e.entity_type,
    e.entity_name,
    a.account_name,
    cf.fiscal_year,
    SUM(cf.amount) as total_amount,
    LAG(SUM(cf.amount)) OVER (PARTITION BY e.entity_id ORDER BY cf.fiscal_year) as prior_year,
    (SUM(cf.amount) - LAG(SUM(cf.amount)) OVER (...)) / LAG(...) * 100 as growth_pct
FROM fact_cashflow cf
JOIN dim_entity e ON cf.entity_id = e.entity_id
JOIN dim_account a ON cf.account_id = a.account_id
WHERE a.account_id = 'REV_TOTAL'
GROUP BY e.entity_type, e.entity_name, a.account_name, cf.fiscal_year
ORDER BY cf.fiscal_year;
```

---

## Open Questions

1. Should Chicago budget data be sourced from Socrata API or CAFR PDF parsing?
2. How to handle different fiscal year ends (Chicago: Dec 31, Companies: varies)?
3. Should we include SEC EDGAR as a direct data source for XBRL financials?
4. How granular should the account hierarchy be (3 levels? 5 levels?)?

---

## References

- Alpha Vantage API Documentation: https://www.alphavantage.co/documentation/
- GASB (Municipal Accounting Standards): https://www.gasb.org/
- GAAP Taxonomy: https://xbrl.us/
- Chicago Data Portal Budget: https://data.cityofchicago.org/
- SEC EDGAR XBRL: https://www.sec.gov/structureddata
