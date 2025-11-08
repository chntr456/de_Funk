# Models System - Universal Session

## Overview

**UniversalSession** is the entry point for multi-model data access. It manages model lifecycles, provides cross-model queries, and injects dependencies between models.

## Class Definition

```python
# File: models/api/session.py:19-250

class UniversalSession:
    """Model-agnostic session for accessing all models."""

    def __init__(self, connection, storage_cfg, repo_root, models=None):
        self.connection = connection
        self.storage_cfg = storage_cfg
        self.repo_root = repo_root
        
        # Model registry
        from models.registry import ModelRegistry
        models_dir = repo_root / "configs" / "models"
        self.registry = ModelRegistry(models_dir)
        
        # Loaded model instances
        self._models: Dict[str, BaseModel] = {}
        
        # Pre-load specified models
        if models:
            for model_name in models:
                self.load_model(model_name)

    @property
    def backend(self) -> str:
        """Detect backend type (spark or duckdb)."""
        connection_type = str(type(self.connection))
        
        if 'spark' in connection_type.lower():
            return 'spark'
        elif 'duckdb' in connection_type.lower():
            return 'duckdb'
        else:
            raise ValueError(f"Unknown connection type: {connection_type}")

    def load_model(self, model_name: str):
        """
        Dynamically load a model.

        Steps:
        1. Get config from registry (YAML)
        2. Get model class from registry (Python)
        3. Instantiate model
        4. Inject session for cross-model access
        5. Cache instance
        """
        if model_name in self._models:
            return self._models[model_name]
        
        # Get config and class
        model_config = self.registry.get_model_config(model_name)
        model_class = self.registry.get_model_class(model_name)
        
        # Instantiate
        model = model_class(
            connection=self.connection,
            storage_cfg=self.storage_cfg,
            model_cfg=model_config,
            params={}
        )
        
        # Inject session
        if hasattr(model, 'set_session'):
            model.set_session(self)
        
        # Cache
        self._models[model_name] = model
        return model
```

## Multi-Model Access

### Get Table from Any Model

```python
def get_table(self, model_name: str, table_name: str, use_cache: bool = True):
    """
    Get a table from any model.

    Args:
        model_name: Name of the model (e.g., 'company')
        table_name: Name of the table (e.g., 'fact_prices')
        use_cache: Use cached model instance

    Returns:
        DataFrame (Spark or DuckDB)
    """
    # Load model if needed
    if model_name not in self._models:
        self.load_model(model_name)
    
    # Get table from model
    model = self._models[model_name]
    return model.get_table(table_name)
```

### Get Model Instance

```python
def get_model_instance(self, model_name: str):
    """
    Get a model instance for calling model-specific methods.

    Usage:
        company = session.get_model_instance('company')
        prices = company.get_prices('AAPL')
    """
    if model_name not in self._models:
        self.load_model(model_name)
    
    return self._models[model_name]
```

## Cross-Model Queries

### Join Across Models

```python
# Get tables from different models
session = UniversalSession(conn, storage, repo_root, models=['company', 'forecast'])

prices = session.get_table('company', 'fact_prices')
forecasts = session.get_table('forecast', 'fact_forecasts')

# Join across models
combined = prices.join(
    forecasts,
    on=['ticker', 'date'],
    how='left'
)
```

### Model Dependencies

Models can access each other via session injection:

```python
class ForecastModel(BaseModel):
    """Forecast model depends on company model."""

    def set_session(self, session):
        """Inject session for cross-model access."""
        self.session = session

    def train(self, ticker: str):
        """Train forecast using company data."""
        # Access company model
        company = self.session.get_model_instance('company')
        
        # Get historical prices
        prices = company.get_prices(ticker)
        
        # Train model
        forecast = self._train_arima(prices)
        return forecast
```

## Usage Patterns

### Pattern 1: Pre-load Models

```python
# Pre-load multiple models
session = UniversalSession(
    connection=conn,
    storage_cfg=storage,
    repo_root=repo_root,
    models=['company', 'forecast', 'macro']
)

# All models ready to use
prices = session.get_table('company', 'fact_prices')
forecasts = session.get_table('forecast', 'fact_forecasts')
gdp = session.get_table('macro', 'fact_gdp')
```

### Pattern 2: Lazy Loading

```python
# Don't pre-load
session = UniversalSession(conn, storage, repo_root)

# Load on demand
prices = session.get_table('company', 'fact_prices')  # Loads company model
```

### Pattern 3: Model-Specific Methods

```python
# Get model instance for domain methods
session = UniversalSession(conn, storage, repo_root)

company = session.get_model_instance('company')
prices = company.get_prices('AAPL')  # Domain-specific method
news = company.get_news('AAPL', start_date='2024-01-01')
```

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/models-system/universal-session.md`
