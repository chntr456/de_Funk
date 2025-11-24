# Technology Stack

**Languages, frameworks, and tools used in de_Funk**

---

## Core Technologies

| Technology | Purpose | Version |
|------------|---------|---------|
| **Python** | Primary language | 3.x |
| **DuckDB** | Analytics engine (primary) | Latest |
| **PySpark** | ETL/transformations (optional) | 3.x |
| **Streamlit** | Web UI framework | Latest |

---

## Data Processing

### DuckDB (Primary Backend)

**Purpose**: High-performance analytics engine

**Advantages**:
- 10-100x faster than Spark for analytics
- No cluster setup required
- Native Parquet support
- SQL interface

**Usage**:
```python
from core.session.universal_session import UniversalSession

session = UniversalSession(backend="duckdb")
df = session.query("SELECT * FROM stocks.dim_stock")
```

### PySpark (Optional Backend)

**Purpose**: Large-scale ETL and distributed processing

**When to Use**:
- Processing datasets larger than memory
- Running on distributed clusters
- Complex ETL transformations

**Usage**:
```python
session = UniversalSession(backend="spark")
```

### Pandas

**Purpose**: Data manipulation and analysis

**Features**:
- DataFrame operations
- Data cleaning
- Analysis and aggregation

### PyArrow

**Purpose**: Parquet file support

**Features**:
- Fast Parquet read/write
- Columnar data format
- Schema preservation

---

## Configuration & Parsing

### PyYAML

**Purpose**: YAML configuration parsing

**Usage**: Model definitions, settings

```yaml
model: stocks
version: 2.0
depends_on: [core, company]
```

### JSON

**Purpose**: API endpoint configurations

**Files**:
- `configs/alpha_vantage_endpoints.json`
- `configs/bls_endpoints.json`
- `configs/chicago_endpoints.json`
- `configs/storage.json`

---

## Visualization

### Plotly

**Purpose**: Interactive charts

**Chart Types**:
- Line charts (time series)
- Bar charts (comparisons)
- Scatter plots (correlations)
- Candlestick charts (OHLC)

**Integration**: Streamlit exhibits

```python
import plotly.express as px

fig = px.line(df, x='date', y='close_price', color='ticker')
st.plotly_chart(fig)
```

---

## Machine Learning / Forecasting

### Statsmodels

**Purpose**: Statistical models

**Models Used**:
- ARIMA (time series)
- Regression analysis

### Prophet

**Purpose**: Facebook's time series forecasting

**Features**:
- Automatic seasonality detection
- Holiday effects
- Trend changepoints

### Scikit-learn

**Purpose**: Machine learning models

**Models Used**:
- RandomForest (forecasting)
- Regression models

---

## Graph Management

### NetworkX

**Purpose**: Model dependency graph

**Features**:
- DAG representation
- Topological sorting
- Dependency resolution

**Usage**:
```python
import networkx as nx

G = nx.DiGraph()
G.add_edge("stocks", "core")
G.add_edge("stocks", "company")
build_order = list(nx.topological_sort(G))
```

---

## Web Framework

### Streamlit

**Purpose**: Interactive web UI

**Features**:
- Rapid prototyping
- Session state management
- Component-based UI

**Application Files**:
- `app/ui/notebook_app_duckdb.py`
- `app/ui/components/`

---

## HTTP & API

### Requests

**Purpose**: HTTP client for API calls

**Features**:
- GET/POST requests
- Rate limiting support
- Retry logic

### Custom HTTP Client

**File**: `datapipelines/base/http_client.py`

**Features**:
- API key rotation
- Exponential backoff
- Request logging

---

## Testing

### pytest

**Purpose**: Testing framework

**Features**:
- Fixtures
- Parametrized tests
- Plugin ecosystem

**Configuration**: `pytest.ini`

```ini
[pytest]
pythonpath = .
testpaths = tests, scripts/test
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow-running tests
```

---

## File Formats

### Parquet

**Purpose**: Columnar data storage

**Advantages**:
- Efficient compression
- Column pruning
- Predicate pushdown
- Schema evolution

**Usage**: All Bronze and Silver data

### Markdown

**Purpose**: Documentation and notebooks

**Features**:
- Notebook content
- Filter syntax: `$filter${...}`
- Exhibit syntax: `$exhibits${...}`

---

## Environment & Configuration

### python-dotenv

**Purpose**: Environment variable management

**File**: `.env`

```bash
ALPHA_VANTAGE_API_KEYS=your_key_here
BLS_API_KEYS=your_key_here
CONNECTION_TYPE=duckdb
```

### Dataclasses

**Purpose**: Type-safe configuration

**Files**: `config/models.py`

```python
@dataclass
class AppConfig:
    repo_root: Path
    connection: ConnectionConfig
    storage: Dict
    apis: Dict
```

---

## Development Tools

### Git

**Purpose**: Version control

**Conventions**:
- Branch naming: `claude/{feature}-{id}`
- Commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`

### VS Code / IDE

**Recommended Extensions**:
- Python
- YAML
- Markdown
- DuckDB

---

## Dependency Summary

```
# Core
python>=3.8
duckdb
pyspark (optional)
pandas
pyarrow

# Web
streamlit
plotly

# ML/Forecasting
statsmodels
prophet
scikit-learn

# Graph
networkx

# Config
pyyaml
python-dotenv

# Testing
pytest

# HTTP
requests
```

---

## Related Documentation

- [Architecture](architecture.md) - System design
- [Configuration](../11-configuration/README.md) - Config system
- [Testing Guide](../10-testing-guide/README.md) - Test patterns
