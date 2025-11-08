# Models System - Model Registry

## Overview

**ModelRegistry** discovers models from YAML configs and manages model class registration. It enables dynamic model loading and configuration-driven development.

## Class Structure

```python
# File: models/registry.py:1-150

class ModelRegistry:
    """Central registry for models."""

    def __init__(self, models_dir: Path):
        """
        Initialize registry.

        Args:
            models_dir: Directory containing model YAML configs
        """
        self.models_dir = models_dir
        self._model_classes = {}  # model_name -> ModelClass
        self._register_builtin_models()

    def _register_builtin_models(self):
        """Register built-in model classes."""
        from models.company.model import CompanyModel
        from models.forecast.model import ForecastModel
        
        self._model_classes['company'] = CompanyModel
        self._model_classes['forecast'] = ForecastModel

    def list_models(self) -> List[str]:
        """List all available models."""
        yaml_files = self.models_dir.glob('*.yaml')
        return [f.stem for f in yaml_files]

    def get_model_config(self, model_name: str) -> Dict:
        """
        Load model configuration from YAML.

        Args:
            model_name: Name of model

        Returns:
            Parsed YAML config dict
        """
        config_path = self.models_dir / f"{model_name}.yaml"
        
        if not config_path.exists():
            raise ValueError(f"Model config not found: {config_path}")
        
        with open(config_path) as f:
            return yaml.safe_load(f)

    def get_model_class(self, model_name: str):
        """
        Get model class for a model name.

        Args:
            model_name: Name of model

        Returns:
            Model class (subclass of BaseModel)
        """
        if model_name not in self._model_classes:
            raise ValueError(f"Model class not registered: {model_name}")
        
        return self._model_classes[model_name]

    def register_model_class(self, model_name: str, model_class):
        """
        Register a custom model class.

        Args:
            model_name: Name to register under
            model_class: BaseModel subclass
        """
        self._model_classes[model_name] = model_class
```

## Model Configuration Structure

```yaml
# configs/models/company.yaml
model: company
version: 1
tags:
  - financial
  - stock-market

# Graph structure
graph:
  nodes:
    - id: fact_prices
      from: bronze.polygon.prices_daily
      select:
        date: date
        ticker: ticker
        close: close

    - id: dim_companies
      from: silver.companies

  edges:
    - from: fact_prices
      to: dim_companies
      on: ticker = ticker

  paths:
    - id: prices_enriched
      from: fact_prices
      joins:
        - dim_companies

# Measures (optional)
measures:
  avg_close:
    description: "Average closing price"
    source: fact_prices.close
    aggregation: avg
    data_type: double
```

## Dynamic Model Loading

```python
# Discover and load models dynamically
registry = ModelRegistry(Path("configs/models"))

# List available models
models = registry.list_models()
print(models)  # ['company', 'forecast', 'macro']

# Load config
company_config = registry.get_model_config('company')

# Get class
CompanyModelClass = registry.get_model_class('company')

# Instantiate
model = CompanyModelClass(conn, storage_cfg, company_config)
```

## Adding Custom Models

### Step 1: Create Model Config

```yaml
# configs/models/portfolio.yaml
model: portfolio
version: 1

graph:
  nodes:
    - id: fact_positions
      from: silver.positions
    
    - id: dim_portfolios
      from: silver.portfolios
  
  edges:
    - from: fact_positions
      to: dim_portfolios
      on: portfolio_id = portfolio_id
```

### Step 2: Create Model Class

```python
# models/portfolio/model.py

from models.base.model import BaseModel

class PortfolioModel(BaseModel):
    """Portfolio tracking model."""

    def get_positions(self, portfolio_id: str):
        """Get positions for a portfolio."""
        positions = self.get_table('fact_positions')
        return self.connection.apply_filters(
            positions,
            {'portfolio_id': portfolio_id}
        )

    def get_holdings(self, portfolio_id: str):
        """Get current holdings."""
        positions = self.get_positions(portfolio_id)
        # Aggregate to get current holdings
        return positions.groupBy('ticker').agg(
            F.sum('quantity').alias('total_quantity'),
            F.avg('cost_basis').alias('avg_cost')
        )
```

### Step 3: Register Model

```python
# Register in registry
registry = ModelRegistry(models_dir)
registry.register_model_class('portfolio', PortfolioModel)

# Now can use it
session = UniversalSession(conn, storage, repo_root)
positions = session.get_table('portfolio', 'fact_positions')
```

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/models-system/model-registry.md`
