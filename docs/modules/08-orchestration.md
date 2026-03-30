---
title: "Orchestration"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/orchestration/checkpoint.py
  - src/de_funk/orchestration/common/path_utils.py
  - src/de_funk/orchestration/common/spark_session.py
  - src/de_funk/orchestration/dependency_graph.py
  - src/de_funk/orchestration/scheduler.py
---

# Orchestration

> Pipeline scheduling, dependency resolution, and checkpointing.

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

### TickerCheckpoint

**File**: `src/de_funk/orchestration/checkpoint.py:26`

**Purpose**: Checkpoint state for a single ticker.

| Attribute | Type |
|-----------|------|
| `ticker` | `str` |
| `status` | `str` |
| `started_at` | `Optional[str]` |
| `completed_at` | `Optional[str]` |
| `error` | `Optional[str]` |
| `retries` | `int` |
| `data_endpoints` | `Dict[str, str]` |

| Method | Description |
|--------|-------------|
| `to_dict() -> dict` | <!-- TODO --> |
| `from_dict(data: dict) -> 'TickerCheckpoint'` | <!-- TODO --> |

### PipelineCheckpoint

**File**: `src/de_funk/orchestration/checkpoint.py:45`

**Purpose**: Checkpoint state for an entire pipeline run.

| Attribute | Type |
|-----------|------|
| `pipeline_id` | `str` |
| `pipeline_name` | `str` |
| `started_at` | `str` |
| `last_updated` | `str` |
| `status` | `str` |
| `total_tickers` | `int` |
| `processed_count` | `int` |
| `failed_count` | `int` |
| `tickers` | `Dict[str, TickerCheckpoint]` |
| `metadata` | `Dict[str, Any]` |

| Method | Description |
|--------|-------------|
| `to_dict() -> dict` | <!-- TODO --> |
| `from_dict(data: dict) -> 'PipelineCheckpoint'` | <!-- TODO --> |

### CheckpointManager

**File**: `src/de_funk/orchestration/checkpoint.py:70`

**Purpose**: Manages checkpoint state for ingestion pipelines.

| Attribute | Type |
|-----------|------|
| `DEFAULT_CHECKPOINT_DIR` | `—` |

| Method | Description |
|--------|-------------|
| `create_checkpoint(pipeline_name: str, tickers: List[str], metadata: Dict[str, Any]) -> PipelineCheckpoint` | Create a new checkpoint for a pipeline run. |
| `load_checkpoint(pipeline_id: str) -> Optional[PipelineCheckpoint]` | Load an existing checkpoint. |
| `find_latest_checkpoint(pipeline_name: str) -> Optional[PipelineCheckpoint]` | Find the most recent checkpoint for a pipeline. |
| `find_resumable_checkpoint(pipeline_name: str) -> Optional[PipelineCheckpoint]` | Find a checkpoint that can be resumed (not completed). |
| `mark_ticker_started(ticker: str) -> None` | Mark a ticker as started processing. |
| `mark_ticker_completed(ticker: str, endpoints: Dict[str, str]) -> None` | Mark a ticker as completed. |
| `mark_ticker_failed(ticker: str, error: str) -> None` | Mark a ticker as failed. |
| `get_pending_tickers() -> List[str]` | Get list of tickers that still need processing. |
| `get_failed_tickers() -> List[str]` | Get list of failed tickers. |
| `mark_pipeline_completed() -> None` | Mark the entire pipeline as completed. |
| `mark_pipeline_failed(error: str) -> None` | Mark the entire pipeline as failed. |
| `get_progress() -> Dict[str, Any]` | Get current progress summary. |
| `clear_checkpoint(pipeline_id: str) -> bool` | Clear a checkpoint file. |
| `list_checkpoints() -> List[Dict[str, Any]]` | List all available checkpoints. |

### ModelInfo

**File**: `src/de_funk/orchestration/dependency_graph.py:53`

**Purpose**: Metadata about a model for dependency resolution.

| Attribute | Type |
|-----------|------|
| `name` | `str` |
| `version` | `str` |
| `depends_on` | `List[str]` |
| `inherits_from` | `Optional[str]` |
| `storage_root` | `str` |
| `enabled` | `bool` |

### DependencyGraph

**File**: `src/de_funk/orchestration/dependency_graph.py:63`

**Purpose**: Model dependency graph with topological sorting.

| Method | Description |
|--------|-------------|
| `build(force: bool) -> None` | Build dependency graph by discovering model configs. |
| `get_dependencies(model_name: str, recursive: bool) -> List[str]` | Get dependencies for a model. |
| `topological_sort() -> List[str]` | Get all models in correct build order. |
| `filter_buildable(requested: List[str]) -> List[str]` | Get build order for specific models with their dependencies. |
| `get_dependents(model_name: str) -> List[str]` | Get models that depend on this model. |
| `visualize() -> str` | Generate text visualization of dependency graph. |
| `get_tiers() -> Dict[int, List[str]]` | Get models organized by dependency tier. |
| `list_models() -> List[str]` | Get list of all discovered models. |
| `get_model_info(model_name: str) -> Optional[ModelInfo]` | Get info for a specific model. |
| `validate() -> List[str]` | Validate the dependency graph. |

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
| `src/de_funk/orchestration/checkpoint.py` | Checkpoint System - Resume capability for long-running ingestion pipelines. | `TickerCheckpoint`, `PipelineCheckpoint`, `CheckpointManager` |
| `src/de_funk/orchestration/common/path_utils.py` | — | — |
| `src/de_funk/orchestration/common/spark_session.py` | — | — |
| `src/de_funk/orchestration/dependency_graph.py` | Dependency Graph - Model build ordering via topological sort. | `ModelInfo`, `DependencyGraph` |
| `src/de_funk/orchestration/scheduler.py` | — | — |
