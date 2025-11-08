# Architecture TODO - BaseModel Writing Abstraction

## Issue: Duplicate Writing Logic

You correctly identified that `company_silver_builder.py` is duplicating functionality that should be in `BaseModel`.

### Current Problematic Architecture

**File:** `models/implemented/company/company_silver_builder.py`

This file:
- Manually builds dimension tables (e.g., `build_dim_company()`)
- Manually builds fact tables (e.g., `build_fact_prices()`)
- Manually builds joined paths (e.g., `build_prices_with_company()`)
- Manually writes tables using `ParquetLoader`

**Problems:**
1. ✗ Duplicates graph building logic that's already in `BaseModel`
2. ✗ Manually implements what YAML config should define
3. ✗ Each model would need its own custom builder
4. ✗ Not using the scalable architecture we built

### Correct Architecture (Already Implemented!)

**File:** `models/base/model.py` - `BaseModel`

The `BaseModel` already has everything we need:

```python
class BaseModel:
    def build(self) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        """
        Build the model graph from YAML configuration.

        Returns:
            (dimensions, facts) - Both as DataFrames in memory
        """
        nodes = self._build_nodes()        # Load from Bronze + transforms
        self._apply_edges(nodes)           # Validate relationships
        paths = self._materialize_paths(nodes)  # Create joined views

        dims = {k: v for k, v in nodes.items() if k.startswith("dim_")}
        facts = {k: v for k, v in paths.items() if k.startswith("fact_")}

        return dims, facts

    def write_tables(self, output_root: str, format: str = "parquet"):
        """
        Write all tables to storage.

        THIS IS WHAT WE SHOULD USE!
        """
        dims, facts = self.build()

        # Write dimensions
        for name, df in dims.items():
            path = f"{output_root}/dims/{name}"
            df.write.mode("overwrite").parquet(path)

        # Write facts
        for name, df in facts.items():
            path = f"{output_root}/facts/{name}"
            df.write.mode("overwrite").parquet(path)
```

### What Should Happen Instead

**Step 1: Define everything in YAML** (`configs/models/company.yaml`)

```yaml
graph:
  nodes:
    - id: dim_company
      from: bronze.ref_ticker
      transforms:
        - select: ["ticker", "name as company_name", "exchange_code"]
        - add_column:
            name: company_id
            expr: "sha1(ticker)"

    - id: dim_exchange
      from: bronze.exchanges
      transforms:
        - select: ["code as exchange_code", "name as exchange_name"]

    - id: fact_prices
      from: bronze.prices_daily
      transforms:
        - select: ["trade_date", "ticker", "open", "high", "low", "close", "volume"]

  paths:
    - id: prices_with_company
      hops: "fact_prices -> dim_company -> dim_exchange"
```

**Step 2: Use BaseModel to build and write**

```python
from models.implemented.company.model import CompanyModel

# Initialize model
model = CompanyModel(
    connection=spark,
    storage_cfg=storage_cfg,
    model_cfg=model_cfg,
    params={}
)

# Build graph (in memory)
dims, facts = model.build()

# Write to Silver layer
model.write_tables(
    output_root="storage/silver/company",
    format="parquet"
)
```

**That's it!** No manual table building needed.

## Why the Current Code Exists

The `company_silver_builder.py` was created **before** we refactored to the scalable BaseModel architecture. It's now obsolete but still being used by the pipeline.

## Migration Path

### Option 1: Use BaseModel Directly (Recommended)

Update `run_full_pipeline.py`:

```python
def build_company_model(spark, repo_root: Path, storage_cfg: dict):
    """Build company model using BaseModel."""
    from models.implemented.company.model import CompanyModel
    import yaml

    # Load config
    model_cfg = yaml.safe_load(
        (repo_root / "configs" / "models" / "company.yaml").read_text()
    )

    # Initialize model
    model = CompanyModel(
        connection=spark,
        storage_cfg=storage_cfg,
        model_cfg=model_cfg,
        params={}
    )

    # Build and write
    dims, facts = model.build()
    model.write_tables(
        output_root=storage_cfg["roots"]["company_silver"],
        format="parquet"
    )

    print(f"✓ Company model built and written")
    print(f"  - Dimensions: {list(dims.keys())}")
    print(f"  - Facts: {list(facts.keys())}")
```

### Option 2: Add Generic Write Method to BaseModel

If `write_tables()` doesn't exist yet, add it to `BaseModel`:

```python
# models/base/model.py

class BaseModel:
    def write_tables(
        self,
        output_root: str,
        format: str = "parquet",
        mode: str = "overwrite",
        partition_by: Optional[Dict[str, List[str]]] = None
    ):
        """
        Write all tables to storage.

        Args:
            output_root: Root path for output
            format: Output format (parquet, delta, etc.)
            mode: Write mode (overwrite, append, etc.)
            partition_by: Optional dict of table_name -> partition_columns
        """
        dims, facts = self.ensure_built()

        # Write dimensions
        for name, df in dims.items():
            path = f"{output_root}/dims/{name}"
            writer = df.write.mode(mode).format(format)

            if partition_by and name in partition_by:
                writer = writer.partitionBy(partition_by[name])

            writer.save(path)
            print(f"  ✓ Wrote {name}: {df.count()} rows")

        # Write facts
        for name, df in facts.items():
            path = f"{output_root}/facts/{name}"
            writer = df.write.mode(mode).format(format)

            if partition_by and name in partition_by:
                writer = writer.partitionBy(partition_by[name])

            writer.save(path)
            print(f"  ✓ Wrote {name}: {df.count()} rows")
```

## Benefits of Using BaseModel

1. **Single Source of Truth**: Everything defined in YAML
2. **No Code Duplication**: All models use same writing logic
3. **Consistent Behavior**: All models write the same way
4. **Easy to Extend**: Add new models without writing builders
5. **Config-Driven**: 87% config, 13% code
6. **Testable**: Easy to test generic write logic once

## Files to Update

1. `models/base/model.py` - Add `write_tables()` method if missing
2. `run_full_pipeline.py` - Use BaseModel instead of company_silver_builder
3. `models/implemented/company/company_silver_builder.py` - Deprecate or remove
4. Any other scripts using company_silver_builder

## Summary

**Current (Wrong):**
- Manual table building in company_silver_builder.py
- Duplicates BaseModel functionality
- Not scalable

**Correct (Use BaseModel):**
- Define tables in YAML
- Use BaseModel.build() to create tables
- Use BaseModel.write_tables() to persist
- No custom builders needed

The architecture you described is exactly what we should have. The company_silver_builder is legacy code from before the refactoring and should be eliminated in favor of using BaseModel directly.
