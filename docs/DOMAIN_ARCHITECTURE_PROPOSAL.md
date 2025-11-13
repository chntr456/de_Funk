# Domain Architecture Proposal: Equity vs. Corporate Separation

**Created:** 2025-11-13
**Purpose:** Restructure company/equity models to properly separate trading instruments from corporate entities

---

## 🎯 Executive Summary

**Current Problem:**
The `company` model conflates two distinct concepts:
1. **Equity** - A tradable security (ticker) with prices, volume, technical indicators
2. **Corporate** - A legal entity (company) with SEC filings, fundamentals, officers, financials

**Proposed Solution:**
Separate these into distinct models with clear relationships:
- **`equity` model** - Trading data, price/volume, technical analysis (domain: equities)
- **`corporate` model** - Company fundamentals, SEC filings, financials (domain: corporate)
- **Relationship:** `Corporate Entity 1 → N Equity Instruments` (one company can have multiple tickers)

---

## 📊 Current Architecture Analysis

### Current Structure

```
models/
├── implemented/
│   ├── company/          # ❌ CONFLATES equity + corporate
│   │   └── model.py
│   └── etf/
│       └── model.py
├── domains/
│   ├── equities/         # ✓ Has weighting strategies
│   │   ├── __init__.py
│   │   └── weighting.py
│   └── etf/
│       └── weighting.py
└── base/
    └── model.py

configs/models/
└── company.yaml          # ❌ Mixes equity and corporate data
```

### Current company.yaml Schema

```yaml
schema:
  dimensions:
    dim_company:           # ❌ Mix of corporate AND equity attributes
      columns:
        ticker: string             # <- Equity identifier
        company_name: string       # <- Corporate attribute
        exchange_code: string      # <- Equity attribute (where traded)
        company_id: string         # <- Corporate identifier
        market_cap_proxy: double   # <- Could be corporate or equity-derived

  facts:
    fact_prices:           # ✓ Clearly equity data
      columns:
        ticker: string
        trade_date: date
        open/high/low/close/volume

    fact_news:             # ❓ Could be either
      columns:
        ticker: string     # <- References equity
        article_id: string
        title/source/sentiment
```

### Issues with Current Design

| Issue | Description | Impact |
|-------|-------------|--------|
| **Conceptual conflation** | Ticker ≠ Company. A company can have multiple tickers (class A/B shares, ADRs, different exchanges) | Can't model Google (GOOG, GOOGL) properly |
| **Missing corporate data** | No SEC CIK, no financial statements, no SEC filings | Can't do fundamental analysis |
| **Wrong grain** | `dim_company` has `ticker` as PK, but company is the entity | Multiple tickers → duplicated company data |
| **Domain confusion** | Price/volume data lives with corporate identity | Mixes trading domain with corporate domain |
| **Limited extensibility** | Can't add corporate-specific measures (P/E ratio, debt/equity, etc.) | Hard to add fundamentals |

---

## 🏗️ Proposed Architecture

### New Structure

```
models/
├── implemented/
│   ├── equity/           # NEW: Trading instruments
│   │   └── model.py      #   EquityModel
│   ├── corporate/        # NEW: Corporate entities
│   │   └── model.py      #   CorporateModel
│   ├── etf/              # EXISTING
│   │   └── model.py
│   └── company/          # DEPRECATED → migrate to equity + corporate
│       └── model.py
│
├── domains/
│   ├── equities/         # EXPANDED: Equity-specific patterns
│   │   ├── __init__.py
│   │   ├── weighting.py         # ✓ Already exists
│   │   ├── technical.py         # NEW: Technical indicators
│   │   └── risk.py              # NEW: Volatility, beta, etc.
│   │
│   ├── corporate/        # NEW: Corporate-specific patterns
│   │   ├── __init__.py
│   │   ├── fundamentals.py      # P/E, P/B, ROE, etc.
│   │   ├── sec_filings.py       # 10-K, 10-Q, 8-K processing
│   │   └── valuation.py         # DCF, comps, etc.
│   │
│   └── etf/              # EXISTING
│       ├── __init__.py
│       └── weighting.py
│
└── base/
    └── model.py

configs/models/
├── equity.yaml           # NEW: Price/volume/trading data
├── corporate.yaml        # NEW: Fundamentals/filings data
├── etf.yaml              # EXISTING
└── company.yaml          # DEPRECATED (or becomes a view joining equity + corporate)
```

---

## 📐 Domain Definitions

### 1. Equity Domain

**Concept:** Tradable security with a ticker symbol

**Data Sources:**
- Market data providers (Polygon, Yahoo Finance, etc.)
- Exchange data (NASDAQ, NYSE)
- Technical indicators

**Key Entities:**
- `dim_equity` - Equity instrument master
  - `ticker` (PK)
  - `company_id` (FK → corporate.dim_company)
  - `exchange_code`
  - `security_type` (common stock, preferred, ADR, etc.)
  - `share_class` (A, B, C)
  - `listing_date`
  - `delisting_date`

- `fact_equity_prices` - Daily OHLCV data
  - `ticker` (FK)
  - `trade_date`
  - `open`, `high`, `low`, `close`, `volume`
  - `volume_weighted`
  - `adjusted_close` (split/dividend adjusted)

- `fact_equity_technicals` - Technical indicators
  - `ticker`, `trade_date`
  - `sma_20`, `sma_50`, `sma_200`
  - `rsi`, `macd`, `bollinger_upper/lower`
  - `volatility_20d`, `beta`

**Domain Calculations:**
- Weighting strategies (equal, volume, market cap, price, volatility)
- Technical indicators (moving averages, RSI, MACD)
- Risk metrics (volatility, beta, Sharpe ratio)
- Returns (simple, log, risk-adjusted)

**Measures Examples:**
```yaml
measures:
  avg_close_price:
    type: simple
    source: fact_equity_prices.close
    aggregation: avg

  volume_weighted_index:
    type: weighted_aggregate
    source: fact_equity_prices.close
    weighting_method: volume

  volatility_20d:
    type: computed
    source: fact_equity_prices.close
    expression: "STDDEV(close) OVER (PARTITION BY ticker ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)"
```

---

### 2. Corporate Domain

**Concept:** Legal business entity with financials and filings

**Data Sources:**
- SEC EDGAR (filings)
- Financial data providers (Financial Modeling Prep, Alpha Vantage)
- Company websites / investor relations

**Key Entities:**
- `dim_corporate` - Corporate entity master
  - `company_id` (PK) - Internal ID
  - `cik_number` - SEC Central Index Key (unique identifier)
  - `company_name`
  - `legal_name`
  - `incorporation_state`
  - `incorporation_date`
  - `fiscal_year_end`
  - `sector`, `industry`
  - `sic_code`
  - `headquarters_location`
  - `website`

- `dim_corporate_officers` - Key executives
  - `company_id` (FK)
  - `officer_name`
  - `title` (CEO, CFO, etc.)
  - `start_date`, `end_date`

- `fact_sec_filings` - SEC filing metadata
  - `company_id` (FK)
  - `cik_number`
  - `filing_date`
  - `report_date`
  - `filing_type` (10-K, 10-Q, 8-K, etc.)
  - `accession_number`
  - `filing_url`
  - `document_url`

- `fact_financials` - Extracted financial statements
  - `company_id` (FK)
  - `report_date`
  - `report_period` (Q1, Q2, Q3, Q4, FY)
  - `statement_type` (income, balance_sheet, cash_flow)
  - Revenue, EBITDA, Net Income, Total Assets, Total Liabilities, etc.

- `fact_financial_ratios` - Calculated ratios
  - `company_id` (FK)
  - `report_date`
  - `pe_ratio`, `pb_ratio`, `debt_to_equity`
  - `roe`, `roa`, `current_ratio`
  - `gross_margin`, `operating_margin`, `net_margin`

**Domain Calculations:**
- Fundamental ratios (P/E, P/B, P/S, EV/EBITDA)
- Profitability metrics (ROE, ROA, margins)
- Leverage metrics (D/E, interest coverage)
- Growth rates (revenue growth, earnings growth)
- Valuation models (DCF, comps)

**Measures Examples:**
```yaml
measures:
  avg_pe_ratio:
    type: simple
    source: fact_financial_ratios.pe_ratio
    aggregation: avg

  revenue_growth_yoy:
    type: computed
    source: fact_financials.revenue
    expression: "(current.revenue - prior.revenue) / prior.revenue"

  debt_to_equity:
    type: computed
    source: fact_financials
    expression: "total_liabilities / total_equity"
```

---

### 3. Relationship Between Equity and Corporate

**Cardinality:** `1 Corporate Entity` → `N Equity Instruments`

**Examples:**
- **Alphabet Inc.** (corporate entity, CIK: 0001652044)
  - GOOG (Class C shares - no voting rights)
  - GOOGL (Class A shares - voting rights)

- **Berkshire Hathaway** (corporate entity, CIK: 0001067983)
  - BRK.A (Class A shares - ~$500K/share)
  - BRK.B (Class B shares - ~$350/share)

- **Chinese ADRs:**
  - **Alibaba Group** (corporate entity)
    - BABA (NYSE - ADR)
    - 9988.HK (Hong Kong exchange)

**Schema Relationship:**
```yaml
# equity.yaml
schema:
  dimensions:
    dim_equity:
      columns:
        ticker: string           # PK
        company_id: string       # FK → corporate.dim_corporate.company_id
        exchange_code: string
        security_type: string
        share_class: string

  edges:
    - from: dim_equity.company_id
      to: corporate.dim_corporate.company_id    # Cross-model edge!
      type: many_to_one
      description: "Equity belongs to corporate entity"
```

---

## 🔄 Migration Strategy

### Phase 1: Create New Models (Parallel)

**Timeline:** 1 week

1. **Create `configs/models/equity.yaml`**
   - Copy price/volume/trading schema from company.yaml
   - Update `dim_equity` with proper columns
   - Add cross-model edge to corporate

2. **Create `models/implemented/equity/model.py`**
   - Copy from company/model.py
   - Rename methods: `calculate_measure_by_ticker` stays
   - Add equity-specific convenience methods

3. **Create `configs/models/corporate.yaml`**
   - Define new corporate entity schema
   - Start with minimal: `dim_corporate`, `fact_sec_filings`
   - Add measures for fundamental ratios

4. **Create `models/implemented/corporate/model.py`**
   - Inherit from BaseModel
   - Add corporate-specific methods: `calculate_measure_by_company`

**Result:** New models exist alongside `company` model (backward compatible)

---

### Phase 2: Expand Domain Patterns

**Timeline:** 1 week

5. **Expand `models/domains/equities/`**
   - Add `technical.py` - Technical indicator calculations
   - Add `risk.py` - Volatility, beta, VaR calculations
   - These are used by equity model measures

6. **Create `models/domains/corporate/`**
   - Add `fundamentals.py` - Ratio calculations (P/E, ROE, etc.)
   - Add `sec_filings.py` - Filing parsing helpers
   - Add `valuation.py` - DCF, comps models
   - These are used by corporate model measures

**Result:** Rich domain-specific calculation patterns

---

### Phase 3: Data Ingestion for Corporate

**Timeline:** 2-3 weeks

7. **SEC EDGAR Integration**
   - Create `datapipelines/providers/sec/` ingestor
   - Facets for: company facts, filings list, 10-K/10-Q parser
   - Bronze layer: `storage/bronze/sec/`
     - `company_facts/` - Company CIK and basic info
     - `filings/` - Filing metadata
     - `financials/` - Parsed financial statements

8. **CIK → Ticker Mapping**
   - Create bridge table: `ref_cik_ticker_mapping`
   - Source: SEC company tickers JSON endpoint
   - Allows joining corporate ↔ equity

9. **Financial Data Provider** (optional)
   - If SEC parsing is complex, use provider API
   - Options: Financial Modeling Prep, Alpha Vantage, IEX Cloud
   - Easier to get clean financial statement data

**Result:** Corporate data flowing into bronze → silver layers

---

### Phase 4: Update Downstream Dependencies

**Timeline:** 1 week

10. **Update Streamlit Notebooks**
    - Notebooks using `company` model → decide if equity or corporate
    - Most price/volume notebooks → use `equity` model
    - Fundamental analysis notebooks → use `corporate` model
    - Update exhibit configs to reference new models

11. **Update Scripts**
    - `scripts/run_company_pipeline.py` → split into:
      - `scripts/run_equity_pipeline.py`
      - `scripts/run_corporate_pipeline.py`
    - Update orchestrator to handle both

12. **Update Tests**
    - Duplicate company tests for equity and corporate
    - Add tests for cross-model edges
    - Test measure calculations with joined data

**Result:** All downstream code uses new models

---

### Phase 5: Deprecate company Model (Optional)

**Timeline:** 1 week

13. **Create company as View Model** (optional)
    - Keep `company.yaml` as a logical view that joins equity + corporate
    - Backward compatibility for existing code
    - Or mark deprecated and remove after migration

14. **Archive old code**
    - Move to `docs/archive/models/company_legacy/`
    - Update documentation

**Result:** Clean architecture, optional backward compatibility

---

## 📋 Detailed Schema Proposals

### equity.yaml

```yaml
version: 1
model: equity
tags: [equities, trading, market_data]

depends_on:
  - core         # Calendar dimension
  - corporate    # Company entity dimension

storage:
  root: storage/silver/equity
  format: parquet

schema:
  dimensions:
    dim_equity:
      path: dims/dim_equity
      description: "Equity instrument master (tradable securities)"
      columns:
        ticker: string                    # PK - Trading symbol
        company_id: string                # FK → corporate.dim_corporate
        isin: string                      # International Securities ID
        cusip: string                     # US securities ID
        exchange_code: string             # Where traded (NASDAQ, NYSE, etc.)
        exchange_mic: string              # Market Identifier Code
        security_type: string             # common_stock, preferred_stock, adr, etc.
        share_class: string               # A, B, C, common, etc.
        currency: string                  # USD, EUR, etc.
        listing_date: date                # When listed on exchange
        delisting_date: date              # When delisted (null if active)
        is_active: boolean                # Currently trading
        shares_outstanding: long          # Latest shares outstanding
        last_updated: timestamp
      primary_key: [ticker]
      tags: [dim, entity, equity]

    dim_exchange:
      path: dims/dim_exchange
      description: "Exchange reference dimension"
      columns:
        exchange_code: string             # PK
        exchange_name: string
        exchange_mic: string              # Market Identifier Code
        country: string
        timezone: string
        trading_hours: string
      primary_key: [exchange_code]
      tags: [dim, ref, exchange]

  facts:
    fact_equity_prices:
      path: facts/fact_equity_prices
      description: "Daily OHLCV equity prices"
      columns:
        ticker: string                    # FK → dim_equity
        trade_date: date                  # PK component
        open: double
        high: double
        low: double
        close: double                     # Unadjusted close
        adjusted_close: double            # Split/dividend adjusted
        volume: long
        volume_weighted: double           # VWAP
        transactions: long                # Number of trades
        market_cap: double                # close * shares_outstanding
      partitions: [trade_date]
      tags: [fact, prices, timeseries, ohlcv]

    fact_equity_technicals:
      path: facts/fact_equity_technicals
      description: "Technical indicators for equities"
      columns:
        ticker: string                    # FK → dim_equity
        trade_date: date                  # PK component
        # Moving averages
        sma_20: double
        sma_50: double
        sma_200: double
        ema_12: double
        ema_26: double
        # Momentum
        rsi_14: double                    # Relative Strength Index
        macd: double                      # MACD line
        macd_signal: double               # Signal line
        macd_histogram: double
        # Volatility
        bollinger_upper: double
        bollinger_lower: double
        bollinger_middle: double
        atr_14: double                    # Average True Range
        # Volume
        obv: double                       # On-Balance Volume
        # Risk
        volatility_20d: double            # 20-day rolling volatility
        volatility_60d: double
        beta: double                      # Beta vs. market
      partitions: [trade_date]
      tags: [fact, technicals, indicators]

    fact_equity_splits:
      path: facts/fact_equity_splits
      description: "Stock splits and reverse splits"
      columns:
        ticker: string
        ex_date: date                     # Ex-dividend date
        split_ratio: double               # e.g., 2.0 for 2-for-1 split
        split_from: int                   # e.g., 1
        split_to: int                     # e.g., 2
      partitions: [ex_date]
      tags: [fact, corporate_actions]

    fact_equity_dividends:
      path: facts/fact_equity_dividends
      description: "Dividend payments"
      columns:
        ticker: string
        ex_date: date
        payment_date: date
        record_date: date
        declared_date: date
        amount: double                    # Dividend per share
        currency: string
        frequency: string                 # quarterly, annual, etc.
      partitions: [ex_date]
      tags: [fact, corporate_actions]

# Edges define relationships
edges:
  - from: fact_equity_prices.ticker
    to: dim_equity.ticker
    type: many_to_one

  - from: dim_equity.company_id
    to: corporate.dim_corporate.company_id     # Cross-model edge!
    type: many_to_one
    description: "Equity instrument belongs to corporate entity"

  - from: dim_equity.exchange_code
    to: dim_exchange.exchange_code
    type: many_to_one

# Measures
measures:
  # Simple price measures
  avg_close_price:
    description: "Average closing price"
    type: simple
    source: fact_equity_prices.close
    aggregation: avg
    data_type: double
    format: "$#,##0.00"

  total_volume:
    description: "Total trading volume"
    type: simple
    source: fact_equity_prices.volume
    aggregation: sum
    data_type: long
    format: "#,##0"

  avg_market_cap:
    description: "Average market capitalization"
    type: simple
    source: fact_equity_prices.market_cap
    aggregation: avg
    data_type: double
    format: "$#,##0"

  # Weighted indices (cross-ticker aggregates)
  equal_weighted_index:
    description: "Equal weighted price index"
    type: weighted_aggregate
    source: fact_equity_prices.close
    weighting_method: equal
    group_by: [trade_date]

  volume_weighted_index:
    description: "Volume weighted price index"
    type: weighted_aggregate
    source: fact_equity_prices.close
    weighting_method: volume
    weight_column: fact_equity_prices.volume
    group_by: [trade_date]

  market_cap_weighted_index:
    description: "Market cap weighted price index"
    type: weighted_aggregate
    source: fact_equity_prices.close
    weighting_method: market_cap
    weight_column: fact_equity_prices.market_cap
    group_by: [trade_date]

  # Technical measures
  avg_rsi:
    description: "Average RSI across period"
    type: simple
    source: fact_equity_technicals.rsi_14
    aggregation: avg

  avg_volatility:
    description: "Average 20-day volatility"
    type: simple
    source: fact_equity_technicals.volatility_20d
    aggregation: avg

  # Returns
  total_return:
    description: "Total return including dividends"
    type: computed
    expression: |
      (end_price - start_price + dividends) / start_price
```

---

### corporate.yaml

```yaml
version: 1
model: corporate
tags: [corporate, fundamentals, sec, filings]

depends_on:
  - core

storage:
  root: storage/silver/corporate
  format: parquet

schema:
  dimensions:
    dim_corporate:
      path: dims/dim_corporate
      description: "Corporate entity master (legal business entities)"
      columns:
        company_id: string                # PK - Internal ID
        cik_number: string                # SEC Central Index Key (10 digits, padded)
        company_name: string              # DBA name
        legal_name: string                # Legal name
        former_names: string              # JSON array of former names
        # Incorporation
        incorporation_state: string       # e.g., "DE" for Delaware
        incorporation_country: string     # e.g., "US"
        incorporation_date: date
        # Fiscal
        fiscal_year_end: string           # e.g., "1231" for Dec 31
        # Classification
        sector: string                    # GICS sector
        industry: string                  # GICS industry
        sic_code: string                  # Standard Industrial Classification
        sic_description: string
        naics_code: string                # North American Industry Classification
        # Location
        headquarters_address: string
        headquarters_city: string
        headquarters_state: string
        headquarters_country: string
        headquarters_zip: string
        # Contact
        phone: string
        website: string
        # Metadata
        is_active: boolean
        last_updated: timestamp
      primary_key: [company_id]
      tags: [dim, entity, corporate]

    dim_corporate_officers:
      path: dims/dim_corporate_officers
      description: "Corporate officers and key executives"
      columns:
        company_id: string                # FK → dim_corporate
        officer_id: string                # PK
        officer_name: string
        title: string                     # CEO, CFO, COO, etc.
        start_date: date
        end_date: date                    # null if current
        is_current: boolean
      primary_key: [officer_id]
      tags: [dim, corporate, officers]

  facts:
    fact_sec_filings:
      path: facts/fact_sec_filings
      description: "SEC filing metadata (all forms)"
      columns:
        company_id: string                # FK → dim_corporate
        cik_number: string
        accession_number: string          # PK - Unique filing ID
        filing_date: date                 # Date filed with SEC
        report_date: date                 # Period end date for report
        filing_type: string               # 10-K, 10-Q, 8-K, S-1, etc.
        film_number: string               # SEC film number
        document_count: int               # Number of documents in filing
        primary_document: string          # Primary document filename
        primary_doc_url: string           # Direct URL to document
        filing_url: string                # EDGAR filing page URL
        items: string                     # JSON array of Item numbers (for 8-K)
        amendment: boolean                # Is this an amendment?
      partitions: [filing_date]
      primary_key: [accession_number]
      tags: [fact, sec, filings]

    fact_financials:
      path: facts/fact_financials
      description: "Financial statement line items (parsed from filings)"
      columns:
        company_id: string                # FK → dim_corporate
        report_date: date                 # Period end date (PK component)
        report_period: string             # Q1, Q2, Q3, Q4, FY
        fiscal_year: int
        fiscal_quarter: int
        statement_type: string            # income, balance_sheet, cash_flow
        filed_date: date                  # When filed
        accession_number: string          # FK → fact_sec_filings
        # Income Statement
        revenue: double
        cost_of_revenue: double
        gross_profit: double
        operating_expenses: double
        operating_income: double
        ebitda: double
        interest_expense: double
        pretax_income: double
        income_tax: double
        net_income: double
        eps_basic: double                 # Earnings per share
        eps_diluted: double
        shares_basic: long                # Weighted avg shares outstanding
        shares_diluted: long
        # Balance Sheet
        total_assets: double
        current_assets: double
        cash_and_equivalents: double
        accounts_receivable: double
        inventory: double
        total_liabilities: double
        current_liabilities: double
        long_term_debt: double
        total_equity: double
        retained_earnings: double
        # Cash Flow
        operating_cash_flow: double
        investing_cash_flow: double
        financing_cash_flow: double
        capex: double                     # Capital expenditures
        free_cash_flow: double            # OCF - capex
        dividends_paid: double
      partitions: [report_date]
      tags: [fact, financials, statements]

    fact_financial_ratios:
      path: facts/fact_financial_ratios
      description: "Calculated financial ratios"
      columns:
        company_id: string
        report_date: date
        # Valuation ratios (requires equity price data)
        pe_ratio: double                  # Price to Earnings
        pb_ratio: double                  # Price to Book
        ps_ratio: double                  # Price to Sales
        pcf_ratio: double                 # Price to Cash Flow
        ev_to_ebitda: double              # Enterprise Value to EBITDA
        # Profitability ratios
        gross_margin: double              # Gross profit / revenue
        operating_margin: double          # Operating income / revenue
        net_margin: double                # Net income / revenue
        roe: double                       # Return on Equity
        roa: double                       # Return on Assets
        roic: double                      # Return on Invested Capital
        # Liquidity ratios
        current_ratio: double             # Current assets / current liabilities
        quick_ratio: double               # (Current assets - inventory) / current liabilities
        cash_ratio: double
        # Leverage ratios
        debt_to_equity: double
        debt_to_assets: double
        interest_coverage: double         # EBIT / interest expense
        # Efficiency ratios
        asset_turnover: double            # Revenue / total assets
        receivables_turnover: double
        inventory_turnover: double
        # Growth rates (YoY)
        revenue_growth_yoy: double
        net_income_growth_yoy: double
        eps_growth_yoy: double
      partitions: [report_date]
      tags: [fact, ratios, calculated]

# Edges
edges:
  - from: fact_sec_filings.company_id
    to: dim_corporate.company_id
    type: many_to_one

  - from: fact_financials.company_id
    to: dim_corporate.company_id
    type: many_to_one

  - from: fact_financial_ratios.company_id
    to: dim_corporate.company_id
    type: many_to_one

  - from: dim_corporate_officers.company_id
    to: dim_corporate.company_id
    type: many_to_one

# Measures
measures:
  # Fundamental measures
  avg_revenue:
    description: "Average revenue"
    type: simple
    source: fact_financials.revenue
    aggregation: avg
    filter: "statement_type = 'income' AND report_period = 'FY'"

  avg_net_income:
    description: "Average net income"
    type: simple
    source: fact_financials.net_income
    aggregation: avg
    filter: "statement_type = 'income' AND report_period = 'FY'"

  avg_total_assets:
    description: "Average total assets"
    type: simple
    source: fact_financials.total_assets
    aggregation: avg
    filter: "statement_type = 'balance_sheet'"

  # Ratio measures
  avg_pe_ratio:
    description: "Average P/E ratio"
    type: simple
    source: fact_financial_ratios.pe_ratio
    aggregation: avg

  avg_roe:
    description: "Average return on equity"
    type: simple
    source: fact_financial_ratios.roe
    aggregation: avg

  avg_debt_to_equity:
    description: "Average debt to equity ratio"
    type: simple
    source: fact_financial_ratios.debt_to_equity
    aggregation: avg

  # Growth measures
  avg_revenue_growth:
    description: "Average revenue growth (YoY)"
    type: simple
    source: fact_financial_ratios.revenue_growth_yoy
    aggregation: avg

  # Filing count
  filing_count:
    description: "Number of SEC filings"
    type: simple
    source: fact_sec_filings.accession_number
    aggregation: count
```

---

## 🔗 Cross-Model Integration Examples

### Example 1: Join Equity Prices with Corporate Fundamentals

**Use case:** Calculate P/E ratio from latest price and TTM earnings

```python
# equity_model.py
def get_prices_with_fundamentals(self, tickers=None):
    """
    Join equity prices with corporate fundamentals.

    Returns prices enriched with P/E ratio, revenue, etc.
    """
    # Get equity prices
    prices_df = self.get_table('fact_equity_prices')

    # Get corporate fundamentals (via cross-model edge)
    from models.implemented.corporate.model import CorporateModel
    corporate_model = CorporateModel(self.backend, self.storage, self.repo)
    fundamentals_df = corporate_model.get_table('fact_financial_ratios')

    # Join via company_id
    joined_df = prices_df.join(
        fundamentals_df,
        on=[
            prices_df.company_id == fundamentals_df.company_id,
            prices_df.trade_date >= fundamentals_df.report_date  # Latest fundamentals
        ],
        how='left'
    )

    return joined_df
```

### Example 2: Screen Stocks by Fundamental + Technical Criteria

**Use case:** Find stocks with P/E < 15, RSI < 30 (oversold + undervalued)

```python
# Notebook or script
from models.implemented.equity.model import EquityModel
from models.implemented.corporate.model import CorporateModel

equity = EquityModel(ctx.connection, ctx.storage, ctx.repo)
corporate = CorporateModel(ctx.connection, ctx.storage, ctx.repo)

# Get technical screen (oversold)
oversold_equities = equity.calculate_measure(
    'avg_rsi',
    entity_column='ticker',
    filters={'trade_date': {'start': '2024-01-01', 'end': '2024-01-31'}}
)
oversold_tickers = oversold_equities.data[oversold_equities.data['rsi_14'] < 30]['ticker'].tolist()

# Get fundamental screen (undervalued)
undervalued_companies = corporate.calculate_measure(
    'avg_pe_ratio',
    entity_column='company_id',
    filters={'report_date': {'start': '2023-01-01'}}
)
undervalued_company_ids = undervalued_companies.data[
    undervalued_companies.data['pe_ratio'] < 15
]['company_id'].tolist()

# Join to find tickers that meet both criteria
# (requires mapping table or join through dim_equity)
```

---

## 🎓 Domain Patterns to Build

### models/domains/equities/technical.py

```python
"""
Technical indicator calculation strategies.

Provides reusable patterns for calculating technical indicators
from OHLCV data.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class TechnicalIndicatorStrategy(ABC):
    """Base class for technical indicator calculations."""

    @abstractmethod
    def generate_sql(self, adapter, **kwargs) -> str:
        """Generate SQL to calculate this indicator."""
        pass


class SMAStrategy(TechnicalIndicatorStrategy):
    """Simple Moving Average calculation."""

    def __init__(self, period: int = 20):
        self.period = period

    def generate_sql(self, adapter, table_name, value_column, group_by, **kwargs):
        """
        Generate SQL for Simple Moving Average.

        Example output:
        AVG(close) OVER (
            PARTITION BY ticker
            ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
        ) as sma_20
        """
        table_ref = adapter.get_table_reference(table_name)

        return f"""
        SELECT
            {group_by},
            {value_column},
            AVG({value_column}) OVER (
                PARTITION BY {group_by}
                ORDER BY trade_date
                ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
            ) as sma_{self.period}
        FROM {table_ref}
        WHERE {value_column} IS NOT NULL
        """


class RSIStrategy(TechnicalIndicatorStrategy):
    """Relative Strength Index calculation."""

    def __init__(self, period: int = 14):
        self.period = period

    def generate_sql(self, adapter, table_name, value_column, group_by, **kwargs):
        """
        Generate SQL for RSI.

        RSI = 100 - (100 / (1 + RS))
        where RS = Average Gain / Average Loss over period
        """
        table_ref = adapter.get_table_reference(table_name)

        return f"""
        WITH price_changes AS (
            SELECT
                {group_by},
                trade_date,
                {value_column},
                {value_column} - LAG({value_column}) OVER (
                    PARTITION BY {group_by}
                    ORDER BY trade_date
                ) as price_change
            FROM {table_ref}
        ),
        gains_losses AS (
            SELECT
                {group_by},
                trade_date,
                CASE WHEN price_change > 0 THEN price_change ELSE 0 END as gain,
                CASE WHEN price_change < 0 THEN ABS(price_change) ELSE 0 END as loss
            FROM price_changes
        ),
        avg_gains_losses AS (
            SELECT
                {group_by},
                trade_date,
                AVG(gain) OVER (
                    PARTITION BY {group_by}
                    ORDER BY trade_date
                    ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
                ) as avg_gain,
                AVG(loss) OVER (
                    PARTITION BY {group_by}
                    ORDER BY trade_date
                    ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
                ) as avg_loss
            FROM gains_losses
        )
        SELECT
            {group_by},
            trade_date,
            CASE
                WHEN avg_loss = 0 THEN 100
                ELSE 100 - (100 / (1 + (avg_gain / avg_loss)))
            END as rsi_{self.period}
        FROM avg_gains_losses
        """


class VolatilityStrategy(TechnicalIndicatorStrategy):
    """Rolling volatility calculation."""

    def __init__(self, period: int = 20):
        self.period = period

    def generate_sql(self, adapter, table_name, value_column, group_by, **kwargs):
        """Generate SQL for rolling standard deviation (volatility)."""
        table_ref = adapter.get_table_reference(table_name)

        return f"""
        SELECT
            {group_by},
            trade_date,
            {value_column},
            STDDEV({value_column}) OVER (
                PARTITION BY {group_by}
                ORDER BY trade_date
                ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
            ) as volatility_{self.period}d
        FROM {table_ref}
        WHERE {value_column} IS NOT NULL
        """


# Registry for technical indicators
_INDICATOR_REGISTRY = {
    'sma': SMAStrategy,
    'rsi': RSIStrategy,
    'volatility': VolatilityStrategy,
}


def get_technical_indicator_strategy(indicator_type: str, **kwargs) -> TechnicalIndicatorStrategy:
    """
    Factory function to get technical indicator strategy.

    Args:
        indicator_type: Type of indicator ('sma', 'rsi', 'volatility')
        **kwargs: Parameters for the indicator (e.g., period=20)

    Returns:
        TechnicalIndicatorStrategy instance
    """
    strategy_class = _INDICATOR_REGISTRY.get(indicator_type.lower())
    if not strategy_class:
        raise ValueError(
            f"Unknown technical indicator: {indicator_type}. "
            f"Available: {list(_INDICATOR_REGISTRY.keys())}"
        )

    return strategy_class(**kwargs)
```

### models/domains/corporate/fundamentals.py

```python
"""
Corporate fundamental analysis patterns.

Provides reusable patterns for calculating financial ratios
and fundamental metrics.
"""

from abc import ABC, abstractmethod


class FundamentalRatioStrategy(ABC):
    """Base class for fundamental ratio calculations."""

    @abstractmethod
    def generate_sql(self, adapter, **kwargs) -> str:
        """Generate SQL to calculate this ratio."""
        pass


class PERatioStrategy(FundamentalRatioStrategy):
    """Price to Earnings ratio calculation."""

    def generate_sql(self, adapter, financials_table, prices_table, **kwargs):
        """
        Calculate P/E ratio = Stock Price / Earnings Per Share (EPS).

        Requires joining equity prices with financial statements.
        """
        financials_ref = adapter.get_table_reference(financials_table)
        prices_ref = adapter.get_table_reference(prices_table)

        return f"""
        SELECT
            f.company_id,
            p.ticker,
            f.report_date,
            p.close as stock_price,
            f.eps_diluted,
            CASE
                WHEN f.eps_diluted > 0 THEN p.close / f.eps_diluted
                ELSE NULL
            END as pe_ratio
        FROM {financials_ref} f
        INNER JOIN equity.dim_equity e ON f.company_id = e.company_id
        INNER JOIN {prices_ref} p ON e.ticker = p.ticker
        WHERE f.statement_type = 'income'
          AND f.report_period = 'FY'
          AND f.eps_diluted IS NOT NULL
          AND p.trade_date >= f.report_date
          AND p.trade_date < f.report_date + INTERVAL '90 days'
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY f.company_id, f.report_date
            ORDER BY p.trade_date DESC
        ) = 1
        """


class ROEStrategy(FundamentalRatioStrategy):
    """Return on Equity calculation."""

    def generate_sql(self, adapter, financials_table, **kwargs):
        """
        Calculate ROE = Net Income / Shareholder's Equity.
        """
        financials_ref = adapter.get_table_reference(financials_table)

        return f"""
        SELECT
            company_id,
            report_date,
            net_income,
            total_equity,
            CASE
                WHEN total_equity > 0 THEN (net_income / total_equity) * 100
                ELSE NULL
            END as roe_percent
        FROM {financials_ref}
        WHERE statement_type = 'income'
          AND net_income IS NOT NULL
          AND total_equity IS NOT NULL
          AND total_equity > 0
        """


class DebtToEquityStrategy(FundamentalRatioStrategy):
    """Debt to Equity ratio calculation."""

    def generate_sql(self, adapter, financials_table, **kwargs):
        """Calculate D/E = Total Liabilities / Total Equity."""
        financials_ref = adapter.get_table_reference(financials_table)

        return f"""
        SELECT
            company_id,
            report_date,
            total_liabilities,
            total_equity,
            CASE
                WHEN total_equity > 0 THEN total_liabilities / total_equity
                ELSE NULL
            END as debt_to_equity
        FROM {financials_ref}
        WHERE statement_type = 'balance_sheet'
          AND total_liabilities IS NOT NULL
          AND total_equity IS NOT NULL
          AND total_equity > 0
        """


# Registry
_RATIO_REGISTRY = {
    'pe_ratio': PERatioStrategy,
    'roe': ROEStrategy,
    'debt_to_equity': DebtToEquityStrategy,
}


def get_fundamental_ratio_strategy(ratio_type: str) -> FundamentalRatioStrategy:
    """Factory function to get fundamental ratio strategy."""
    strategy_class = _RATIO_REGISTRY.get(ratio_type.lower())
    if not strategy_class:
        raise ValueError(
            f"Unknown fundamental ratio: {ratio_type}. "
            f"Available: {list(_RATIO_REGISTRY.keys())}"
        )

    return strategy_class()
```

---

## 📊 Data Ingestion: SEC EDGAR

### SEC EDGAR API Overview

**Endpoints:**
- **Company Facts:** `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`
  - All XBRL tags for a company
  - Revenue, earnings, assets, etc. across all filings

- **Company Tickers:** `https://www.sec.gov/files/company_tickers.json`
  - Maps CIK → ticker symbol
  - Company name, exchange

- **Submissions:** `https://data.sec.gov/submissions/CIK{cik}.json`
  - All filings metadata for a company
  - Filing dates, accession numbers, forms

### Implementation: datapipelines/providers/sec/

```python
# datapipelines/providers/sec/sec_ingestor.py

import requests
import time
from typing import List, Dict, Any
from pathlib import Path


class SECIngestor:
    """
    Ingestor for SEC EDGAR data.

    Respects SEC rate limits (10 requests/second).
    """

    BASE_URL = "https://data.sec.gov"
    RATE_LIMIT_DELAY = 0.1  # 100ms between requests

    def __init__(self, storage_cfg: Dict[str, Any], user_agent: str):
        """
        Args:
            storage_cfg: Storage configuration with bronze root
            user_agent: Required by SEC (e.g., "YourName your@email.com")
        """
        self.bronze_root = Path(storage_cfg['roots']['bronze'])
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept-Encoding': 'gzip, deflate',
        })
        self.last_request_time = 0

    def _rate_limit(self):
        """Enforce SEC rate limit."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def get_company_tickers(self) -> Dict[str, Any]:
        """
        Get mapping of all CIK → ticker from SEC.

        Returns JSON like:
        {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
            "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
            ...
        }
        """
        self._rate_limit()
        url = f"{self.BASE_URL}/files/company_tickers.json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_company_facts(self, cik: str) -> Dict[str, Any]:
        """
        Get all XBRL facts for a company.

        Args:
            cik: 10-digit CIK (zero-padded)

        Returns JSON with all financial data points.
        """
        self._rate_limit()
        cik_padded = str(cik).zfill(10)
        url = f"{self.BASE_URL}/api/xbrl/companyfacts/CIK{cik_padded}.json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_company_submissions(self, cik: str) -> Dict[str, Any]:
        """
        Get all filing submissions for a company.

        Returns metadata for all 10-K, 10-Q, 8-K, etc. filings.
        """
        self._rate_limit()
        cik_padded = str(cik).zfill(10)
        url = f"{self.BASE_URL}/submissions/CIK{cik_padded}.json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def ingest_all_companies(self, ciks: List[str]):
        """
        Ingest data for multiple companies.

        Creates bronze layer files:
        - bronze/sec/company_facts/{cik}.json
        - bronze/sec/submissions/{cik}.json
        """
        facts_dir = self.bronze_root / 'sec' / 'company_facts'
        submissions_dir = self.bronze_root / 'sec' / 'submissions'

        facts_dir.mkdir(parents=True, exist_ok=True)
        submissions_dir.mkdir(parents=True, exist_ok=True)

        for cik in ciks:
            print(f"Ingesting CIK {cik}...")

            # Get facts
            try:
                facts = self.get_company_facts(cik)
                facts_path = facts_dir / f"{cik}.json"
                facts_path.write_text(json.dumps(facts, indent=2))
            except requests.HTTPError as e:
                print(f"  Error getting facts: {e}")

            # Get submissions
            try:
                submissions = self.get_company_submissions(cik)
                submissions_path = submissions_dir / f"{cik}.json"
                submissions_path.write_text(json.dumps(submissions, indent=2))
            except requests.HTTPError as e:
                print(f"  Error getting submissions: {e}")
```

---

## 🚀 Next Steps

### Immediate Actions (Week 1)

1. **Review and approve this proposal**
   - Discuss domain boundaries
   - Confirm schema designs
   - Approve migration strategy

2. **Create equity.yaml and corporate.yaml**
   - Start with schemas proposed above
   - Adjust based on available data

3. **Create EquityModel and CorporateModel**
   - Copy from CompanyModel
   - Update to use new schemas

4. **Test with existing data**
   - Verify equity model works with existing prices_daily bronze data
   - Ensure backward compatibility

### Medium-term (Weeks 2-4)

5. **Expand domain patterns**
   - Build out `models/domains/equities/technical.py`
   - Build out `models/domains/corporate/fundamentals.py`

6. **Implement SEC EDGAR ingestion**
   - Create SEC ingestor
   - Ingest company facts for top tickers
   - Parse into corporate tables

7. **Update Streamlit notebooks**
   - Migrate exhibits to use equity/corporate models
   - Test end-to-end

### Long-term (Month 2+)

8. **Add advanced features**
   - Valuation models (DCF, comps)
   - Backtesting framework using historical fundamentals
   - Alerts on filing dates

9. **Deprecate company model**
   - Mark as deprecated
   - Provide migration guide
   - Eventually remove

---

## ❓ Open Questions

1. **Should we keep `company` model as a compatibility layer?**
   - Option A: Make it a view that joins equity + corporate
   - Option B: Deprecate immediately
   - Option C: Keep as-is for now, migrate gradually

2. **CIK → Ticker mapping strategy?**
   - Store in bridge table?
   - Add cik_number to dim_equity directly?

3. **Financial data source?**
   - Parse SEC filings directly (complex but free)
   - Use provider API (easier but costs money)
   - Hybrid approach?

4. **How to handle historical equity changes?**
   - Ticker renames (e.g., FB → META)
   - Spin-offs, mergers, acquisitions
   - SCD Type 2 on dim_equity?

5. **Cross-model measure calculations?**
   - Should measures span models (e.g., P/E ratio needs equity + corporate)?
   - Or keep measures within model, join in analysis layer?

---

## 📝 Summary

This proposal separates **trading instruments** (equities) from **corporate entities** (companies) into distinct models with clear boundaries:

- **Equity Model:** Tickers, prices, technical analysis, trading patterns
- **Corporate Model:** Companies, SEC filings, financials, fundamentals
- **Relationship:** 1 company → N equities (via company_id foreign key)

**Benefits:**
- ✅ Proper separation of concerns
- ✅ Can model multi-class shares (GOOG/GOOGL)
- ✅ Foundation for SEC EDGAR integration
- ✅ Enables fundamental analysis
- ✅ Clearer domain patterns

**Migration:**
- Create new models in parallel (backward compatible)
- Gradually migrate notebooks/scripts
- Eventually deprecate company model

**Ready to proceed?** Let's start with creating `equity.yaml` and `corporate.yaml`!
