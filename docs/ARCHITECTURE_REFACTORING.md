# Architecture Refactoring Plan

## Current Problems

### 1. **No Silver Layer Materialization**
- `CompanyModel` reads from Bronze but never writes to Silver
- `ParquetLoader` exists but is never used
- storage.json defines Silver tables but they don't exist

### 2. **Measures Calculated On-the-Fly**
- `MeasureEngine` calculates aggregations at query time
- No pre-computed aggregates in Silver layer
- Every notebook request recomputes from raw data

### 3. **Tight Coupling & No Separation of Concerns**
```
Current Flow:
UI → NotebookSession → GraphQueryEngine → MeasureEngine → ModelSession → CompanyModel → Bronze
```

Problems:
- UI knows about Spark DataFrames
- NotebookSession does graph building, filtering, and measure calculation
- CompanyModel mixes reading, transformation, and serving
- No storage service abstraction

### 4. **CompanyModel Responsibilities Are Mixed**
Current CompanyModel:
- Reads from Bronze (storage layer)
- Builds graph nodes (transformation layer)
- Materializes paths (transformation layer)
- Serves data to notebooks (API layer)

Should be: One responsibility only

## Proposed Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                    │
│  - notebook_app_professional.py                             │
│  - Renders UI only, no business logic                       │
│  - Receives pre-computed Pandas DataFrames                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                        API / SERVICE LAYER                   │
│  - NotebookService (simplified)                             │
│    • Load notebook config                                    │
│    • Apply filters                                           │
│    • Return exhibit data                                     │
│  - No measure calculation                                    │
│  - No graph building                                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                      STORAGE SERVICE LAYER                   │
│  - SilverStorageService                                     │
│    • Read from Silver layer                                  │
│    • Apply simple filters (date range, tickers)             │
│    • Return cached DataFrames                                │
│  - Abstract storage details                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                      SILVER LAYER (Parquet)                  │
│  storage/silver/company/                                    │
│    dims/                                                     │
│      dim_company/                                            │
│      dim_exchange/                                           │
│    facts/                                                    │
│      fact_prices_daily/  (pre-aggregated by date, ticker)  │
│      fact_prices_monthly/ (pre-aggregated by month, ticker) │
│    paths/                                                    │
│      prices_with_company/                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                      ETL / TRANSFORMATION LAYER              │
│  - CompanySilverBuilder                                     │
│    • Read from Bronze                                        │
│    • Build dimension tables                                  │
│    • Pre-calculate ALL measures/aggregations                │
│    • Materialize paths                                       │
│    • Write to Silver using ParquetLoader                    │
│  - Run offline (Airflow/cron)                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                      BRONZE LAYER (Parquet)                  │
│  storage/bronze/                                            │
│    ref_all_tickers/                                          │
│    exchanges/                                                │
│    prices_daily/                                             │
└─────────────────────────────────────────────────────────────┘
```

## Refactoring Steps

### Step 1: Create Silver Layer Builder
**File**: `src/model/silver/company_silver_builder.py`

```python
class CompanySilverBuilder:
    """
    Builds Silver layer from Bronze.

    Responsibilities:
    - Read from Bronze
    - Build dimensions
    - Pre-calculate ALL measures
    - Materialize fact tables with measures
    - Write to Silver using ParquetLoader
    """
```

Pre-computed measures in Silver:
- `fact_prices_daily`: ticker, trade_date, open, high, low, close, volume, vwap
- `fact_prices_monthly`: ticker, month, avg_close, total_volume, max_high, min_low
- `fact_prices_by_ticker`: ticker, avg_close, total_volume, max_high, min_low (all time)

### Step 2: Create Storage Service
**File**: `src/services/storage_service.py`

```python
class SilverStorageService:
    """
    Service for reading from Silver layer.

    Responsibilities:
    - Read Silver layer tables
    - Apply simple filters
    - Return DataFrames
    - Cache results
    """

    def get_dim_company(self, tickers=None) -> DataFrame
    def get_fact_prices_daily(self, start_date, end_date, tickers) -> DataFrame
    def get_prices_with_company(self, start_date, end_date, tickers) -> DataFrame
```

### Step 3: Simplify Notebook Service
**File**: `src/services/notebook_service.py`

```python
class NotebookService:
    """
    Simplified notebook service.

    Responsibilities ONLY:
    - Load notebook config
    - Apply user filters
    - Fetch pre-computed data from SilverStorageService
    - Return Pandas DataFrames
    """

    def __init__(self, storage_service: SilverStorageService)
    def load_notebook(self, path) -> NotebookConfig
    def get_exhibit_data(self, exhibit_id) -> pd.DataFrame
```

**Remove**:
- GraphQueryEngine
- MeasureEngine
- Graph building logic
- Measure calculation logic

### Step 4: Simplify UI
**File**: `src/ui/notebook_app_professional.py`

Changes:
- Use NotebookService instead of NotebookSession
- Receive Pandas DataFrames directly
- Only handle rendering
- No Spark dependencies

### Step 5: Update CompanyModel
**File**: `src/model/company_model.py`

Keep it ONLY for reading Silver layer (used by SilverStorageService):

```python
class CompanyModel:
    """
    Read-only model for Silver layer.

    Responsibilities:
    - Read from Silver layer
    - Return nodes (dims/facts) as DataFrames
    """

    def __init__(self, spark, storage_cfg)
    def get_dim(self, dim_name) -> DataFrame
    def get_fact(self, fact_name) -> DataFrame
```

### Step 6: Build Pipeline Script
**File**: `scripts/build_silver_layer.py`

```python
def build_company_silver(snapshot_date):
    builder = CompanySilverBuilder(spark, storage_cfg)
    builder.build_and_write(snapshot_date)
```

Run this offline to materialize Silver layer.

## Data Flow After Refactoring

### Offline (ETL):
```
Bronze → CompanySilverBuilder → Silver (Parquet)
                                  ↓
                           (Pre-computed measures,
                            aggregated facts,
                            materialized paths)
```

### Online (User Query):
```
User Filter → NotebookService → SilverStorageService → Silver (Read)
                ↓                                          ↓
           Pandas DF                               Cached DF
                ↓
               UI
```

## Benefits

1. **Performance**: Measures pre-computed, no runtime aggregation
2. **Separation**: Clear layer boundaries
3. **Scalability**: Offline ETL can handle large datasets
4. **Simplicity**: Each component has one responsibility
5. **Testability**: Each layer can be tested independently
6. **Storage Abstraction**: Silver layer is source of truth

## Notebook YAML Changes

Simplify to just declare what to show:

```yaml
exhibits:
  - id: price_overview
    type: metric_cards
    source: fact_prices_by_ticker  # Pre-computed in Silver
    filters:
      tickers: $tickers
    metrics:
      - measure: avg_close_price    # Already computed
      - measure: total_volume        # Already computed
```

No measure definitions needed - they're in Silver schema.

## Migration Path

1. Create `CompanySilverBuilder` - build Silver tables
2. Run builder script once to populate Silver
3. Create `SilverStorageService` - read from Silver
4. Create `NotebookService` - use StorageService
5. Update UI to use NotebookService
6. Deprecate old NotebookSession, GraphQueryEngine, MeasureEngine
7. Simplify CompanyModel to read-only Silver access

## File Structure After Refactoring

```
src/
├── model/
│   ├── company_model.py              (read-only Silver access)
│   └── silver/
│       └── company_silver_builder.py (ETL logic)
├── services/
│   ├── storage_service.py            (Silver layer access)
│   └── notebook_service.py           (Simplified)
├── ui/
│   └── notebook_app_professional.py  (Render only)
└── notebook/
    ├── schema.py                      (Keep)
    ├── parser.py                      (Keep)
    └── filters/                       (Keep)
        └── engine.py
```

**Remove**:
- src/notebook/graph/
- src/notebook/measures/
- src/notebook/api/notebook_session.py (replace with simpler service)

## Next Steps

1. Implement `CompanySilverBuilder`
2. Implement `SilverStorageService`
3. Implement simplified `NotebookService`
4. Update UI
5. Test end-to-end
6. Build Silver layer
7. Remove deprecated code
