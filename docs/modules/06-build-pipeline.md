---
title: "Build Pipeline & Hooks"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/models/base/model.py
  - src/de_funk/models/base/domain_model.py
  - src/de_funk/models/base/builder.py
  - src/de_funk/models/base/domain_builder.py
  - src/de_funk/models/base/graph_builder.py
  - src/de_funk/models/base/data_validator.py
  - src/de_funk/core/executor.py
  - src/de_funk/core/hooks.py
  - src/de_funk/core/artifacts.py
  - src/de_funk/core/plugins.py
---

# Build Pipeline & Hooks

> BaseModel → DomainModel → GraphBuilder → NodeExecutor build chain, plus HookRunner and ArtifactStore.

## Purpose & Design Decisions

### What Problem This Solves

<!-- TODO: Explain the problem this group addresses. -->

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| <!-- TODO --> | | |

### Config-Driven Aspects

| Behavior | Controlled By | Location |
|----------|--------------|----------|
| <!-- TODO --> | | |

## Architecture

### Where This Fits

```
[Upstream] --> [THIS GROUP] --> [Downstream]
```

<!-- TODO: Brief explanation of data/control flow. -->

### Dependencies

| Depends On | What For |
|------------|----------|
| <!-- TODO --> | |

| Depended On By | What For |
|----------------|----------|
| <!-- TODO --> | |

## Key Classes

### BaseModel

**File**: `src/de_funk/models/base/model.py:25`

**Purpose**: Build-only model class. Session-first — all ops go through Engine.

| Method | Description |
|--------|-------------|
| `backend() -> str` | Backend type from Engine. |
| `build() -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]` | Build Silver tables via GraphBuilder → NodeExecutor. |
| `ensure_built()` | <!-- TODO --> |
| `write_tables(output_root: str, fmt: str, mode: str)` | Write built tables to Silver via Engine. |
| `get_table(name: str) -> Optional[DataFrame]` | <!-- TODO --> |
| `has_table(name: str) -> bool` | <!-- TODO --> |
| `list_tables() -> List[str]` | <!-- TODO --> |
| `before_build()` | <!-- TODO --> |
| `after_build(dims, facts)` | <!-- TODO --> |
| `custom_node_loading(node_id: str, node_config: Dict) -> Optional[DataFrame]` | <!-- TODO --> |
| `set_session(session)` | Legacy compat — session is set in __init__ now. |

### DomainModel (BaseModel)

**File**: `src/de_funk/models/base/domain_model.py:78`

**Purpose**: BaseModel subclass that handles domain config specifics.

| Method | Description |
|--------|-------------|
| `custom_node_loading(node_id: str, node_config: Dict) -> Optional[DataFrame]` | Handle domain-config-specific node types that GraphBuilder can't process. |
| `graph_builder()` | Access the graph builder (lazy-loaded by BaseModel). |

### BuildResult

**File**: `src/de_funk/models/base/builder.py:22`

**Purpose**: Result of a model build operation.

| Attribute | Type |
|-----------|------|
| `model_name` | `str` |
| `success` | `bool` |
| `dimensions` | `int` |
| `facts` | `int` |
| `rows_written` | `int` |
| `duration_seconds` | `float` |
| `error` | `Optional[str]` |
| `warnings` | `List[str]` |

### BaseModelBuilder

**File**: `src/de_funk/models/base/builder.py:40`

**Purpose**: Abstract builder for domain models. Takes BuildSession directly.

| Attribute | Type |
|-----------|------|
| `model_name` | `str` |
| `depends_on` | `List[str]` |

| Method | Description |
|--------|-------------|
| `get_model_class() -> Type` | Return the model class to instantiate. |
| `get_model_config() -> Dict[str, Any]` | Load model config from domain markdown. |
| `build() -> BuildResult` | Build the model: instantiate → build → write. |
| `get_dependencies() -> List[str]` | <!-- TODO --> |

### BuilderRegistry

**File**: `src/de_funk/models/base/builder.py:139`

**Purpose**: Registry of discovered model builders.

| Attribute | Type |
|-----------|------|
| `_builders` | `Dict[str, Type[BaseModelBuilder]]` |

| Method | Description |
|--------|-------------|
| `register(builder_class: Type[BaseModelBuilder]) -> Type[BaseModelBuilder]` | <!-- TODO --> |
| `all() -> Dict[str, Type[BaseModelBuilder]]` | <!-- TODO --> |
| `discover(models_path: Path) -> None` | Discover builders from Python modules. |
| `clear()` | <!-- TODO --> |

### DomainBuilderFactory

**File**: `src/de_funk/models/base/domain_builder.py:33`

**Purpose**: Factory that scans domain configs and creates builder classes.

| Method | Description |
|--------|-------------|
| `create_builders(domains_dir: Path) -> Dict[str, Any]` | Scan domain configs and create/register builder classes. |

### GraphBuilder

**File**: `src/de_funk/models/base/graph_builder.py:18`

**Purpose**: Builds model tables from Bronze via NodeExecutor + Engine.

| Method | Description |
|--------|-------------|
| `model_cfg() -> Dict` | <!-- TODO --> |
| `build() -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]` | Build model tables: hooks → NodeExecutor → separate dims/facts → hooks. |

### ValidationIssue

**File**: `src/de_funk/models/base/data_validator.py:32`

**Purpose**: Single validation issue.

| Attribute | Type |
|-----------|------|
| `level` | `str` |
| `category` | `str` |
| `message` | `str` |
| `details` | `Dict[str, Any]` |

### ValidationReport

**File**: `src/de_funk/models/base/data_validator.py:44`

**Purpose**: Complete validation report.

| Attribute | Type |
|-----------|------|
| `validator_name` | `str` |
| `timestamp` | `datetime` |
| `issues` | `List[ValidationIssue]` |
| `metrics` | `Dict[str, Any]` |

| Method | Description |
|--------|-------------|
| `is_valid() -> bool` | True if no errors (warnings are OK). |
| `error_count() -> int` | <!-- TODO --> |
| `warning_count() -> int` | <!-- TODO --> |
| `add_error(category: str, message: str)` | Add an error issue. |
| `add_warning(category: str, message: str)` | Add a warning issue. |
| `add_info(category: str, message: str)` | Add an info issue. |
| `summary() -> str` | Generate human-readable summary. |

### DataValidator

**File**: `src/de_funk/models/base/data_validator.py:98`

**Purpose**: Base class for data validation.

| Method | Description |
|--------|-------------|
| `columns() -> Set[str]` | Get column names (cached). |
| `row_count() -> int` | Get row count (cached). |
| `get_required_columns() -> List[str]` | Return list of columns that MUST exist. |
| `get_numeric_columns() -> List[str]` | Return list of columns that should be numeric. |
| `get_date_column() -> Optional[str]` | Return the date column name for time series validation. |
| `get_entity_column() -> Optional[str]` | Return the entity column name (e.g., ticker, indicator_code). |
| `get_optional_columns() -> List[str]` | Return columns that are nice to have but not required. |
| `get_valid_ranges() -> Dict[str, tuple]` | Return valid ranges for numeric columns. |
| `get_min_rows() -> int` | Minimum number of rows required. |
| `get_null_thresholds() -> Dict[str, float]` | Return acceptable null percentage thresholds per column. |
| `validate() -> ValidationReport` | Run all validations and return report. |

### NodeExecutor

**File**: `src/de_funk/core/executor.py:22`

**Purpose**: Config-driven pipeline executor for build operations.

| Method | Description |
|--------|-------------|
| `register_op(name: str, handler: Callable)` | Register a custom pipeline operation. |
| `get_op(name: str) -> Callable | None` | Get an operation handler by name. |
| `list_ops() -> list[str]` | List all registered operation names. |
| `execute_all(nodes_config: dict) -> dict[str, Any]` | Execute all nodes in order, returning {node_id: DataFrame}. |
| `execute_node(node_id: str, config: dict, built: dict) -> Any` | Execute a single node: load source → run pipeline → return DF. |
| `execute_pipeline(df: Any, steps: list) -> Any` | Execute a sequence of pipeline steps on a DataFrame. |

### HookRunner

**File**: `src/de_funk/core/hooks.py:138`

**Purpose**: Dispatches hooks from YAML config, with decorator fallback.

| Method | Description |
|--------|-------------|
| `run(hook_name: str) -> Any` | Run all hooks for a lifecycle event. |
| `has_hooks(hook_name: str) -> bool` | Check if any hooks exist for a lifecycle event. |
| `list_hooks() -> dict` | List all available hooks for this model. |

### ModelArtifact

**File**: `src/de_funk/core/artifacts.py:26`

**Purpose**: Metadata for a trained ML model artifact.

| Attribute | Type |
|-----------|------|
| `model_name` | `str` |
| `version` | `str` |
| `trained_at` | `str` |
| `artifact_path` | `str` |
| `metrics` | `dict` |
| `config` | `dict` |
| `status` | `str` |

| Method | Description |
|--------|-------------|
| `to_dict() -> dict` | <!-- TODO --> |
| `from_dict() -> ModelArtifact` | <!-- TODO --> |

### ArtifactStore

**File**: `src/de_funk/core/artifacts.py:48`

**Purpose**: Manages trained model artifacts on disk.

| Method | Description |
|--------|-------------|
| `save(artifact: ModelArtifact, model_object: Any) -> Path` | Save a trained model artifact + metadata. |
| `load(model_name: str, version: str) -> tuple[ModelArtifact, Any]` | Load a trained model artifact by name and version. |
| `latest(model_name: str) -> tuple[ModelArtifact, Any] | None` | Load the most recent version of a model. |
| `list_versions(model_name: str) -> list[ModelArtifact]` | List all versions of a model, sorted by trained_at. |
| `register(artifact: ModelArtifact) -> None` | Register an artifact (save metadata only, no model object). |

## How to Use

### Common Operations

<!-- TODO: Runnable code examples with expected output -->

### Integration Examples

<!-- TODO: Show cross-group usage -->

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| <!-- TODO --> | | |

### Debug Checklist

- [ ] <!-- TODO -->

### Common Pitfalls

1. <!-- TODO -->

## File Reference

| File | Purpose | Key Exports |
|------|---------|-------------|
| `src/de_funk/models/base/model.py` | BaseModel — builds Silver tables from domain YAML config. | `BaseModel` |
| `src/de_funk/models/base/domain_model.py` | DomainModel - BaseModel subclass for multi-file domain configs. | `DomainModel` |
| `src/de_funk/models/base/builder.py` | BaseModelBuilder — builds Silver tables from domain configs. | `BuildResult`, `BaseModelBuilder`, `BuilderRegistry` |
| `src/de_funk/models/base/domain_builder.py` | Domain Builder Factory - Dynamic builder registration for domain models. | `DomainBuilderFactory` |
| `src/de_funk/models/base/graph_builder.py` | GraphBuilder — builds model tables from Bronze via NodeExecutor. | `GraphBuilder` |
| `src/de_funk/models/base/data_validator.py` | DataValidator - Base class for data validation in model builders. | `ValidationIssue`, `ValidationReport`, `DataValidator` |
| `src/de_funk/core/executor.py` | NodeExecutor — config-driven pipeline executor. | `NodeExecutor` |
| `src/de_funk/core/hooks.py` | HookRunner — config-first hook dispatch. | `HookRunner` |
| `src/de_funk/core/artifacts.py` | Model Artifacts — trained ML model lifecycle management. | `ModelArtifact`, `ArtifactStore` |
| `src/de_funk/core/plugins.py` | Backward compat — imports from core.hooks. | — |
