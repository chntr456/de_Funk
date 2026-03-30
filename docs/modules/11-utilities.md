---
title: "Utilities"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/core/context.py
  - src/de_funk/utils/api_validator.py
  - src/de_funk/utils/env_loader.py
  - src/de_funk/utils/pipeline_tracker.py
  - src/de_funk/utils/repo.py
---

# Utilities

> Repo context, API validator, pipeline tracker — small cross-cutting helpers.

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

### RepoContext

**File**: `src/de_funk/core/context.py:12`

**Purpose**: Repository context with database connection and configuration.

| Attribute | Type |
|-----------|------|
| `repo` | `Path` |
| `spark` | `Any` |
| `storage` | `Dict[str, Any]` |
| `connection` | `Optional[Any]` |
| `connection_type` | `str` |
| `_config` | `Optional[AppConfig]` |

| Method | Description |
|--------|-------------|
| `get_api_config(provider: str) -> Dict[str, Any]` | Get API configuration for any provider. |
| `from_repo_root(connection_type: Optional[str]) -> 'RepoContext'` | Create RepoContext from repository root. |
| `config() -> Optional[AppConfig]` | Get the full typed configuration object. |

### APIValidator

**File**: `src/de_funk/utils/api_validator.py:16`

**Purpose**: Validates Polygon API access and capabilities.

| Method | Description |
|--------|-------------|
| `validate_date_range(date_from: str, date_to: str, auto_adjust: bool) -> Tuple[bool, str, Optional[str]]` | Validate if date range is accessible with current API plan. |
| `test_api_connection() -> Tuple[bool, str]` | Test basic API connection and authentication. |
| `get_recommended_date_range(days: int) -> Tuple[str, str]` | Get a recommended date range that should work with most API plans. |
| `prompt_user_for_adjusted_range(original_to: str, suggested_from: str) -> Tuple[str, str, bool]` | Prompt user to accept adjusted date range or abort. |

### PipelineRunTracker

**File**: `src/de_funk/utils/pipeline_tracker.py:15`

**Purpose**: Tracks pipeline executions and maintains a history log.

| Method | Description |
|--------|-------------|
| `start_run(pipeline_type: str, config: Dict[str, Any]) -> str` | Start tracking a new pipeline run. |
| `log_stage(stage: str, status: str, details: Dict[str, Any])` | Log a pipeline stage completion. |
| `log_error(error: str, stage: str)` | Log an error during pipeline execution. |
| `log_warning(warning: str, stage: str)` | Log a warning during pipeline execution. |
| `update_results(results: Dict[str, Any])` | Update run results. |
| `end_run(status: str, summary: Dict[str, Any])` | End the current pipeline run. |
| `get_recent_runs(count: int) -> list` | Get recent pipeline runs. |
| `print_recent_runs(count: int)` | Print recent pipeline runs. |

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
| `src/de_funk/core/context.py` | — | `RepoContext` |
| `src/de_funk/utils/api_validator.py` | API Validation Utility | `APIValidator` |
| `src/de_funk/utils/env_loader.py` | Environment Variable Loader for de_Funk | — |
| `src/de_funk/utils/pipeline_tracker.py` | Pipeline Run Tracker | `PipelineRunTracker` |
| `src/de_funk/utils/repo.py` | Centralized repository path and import management. | — |
