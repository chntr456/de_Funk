---
title: "Application"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/app.py
---

# Application

> DeFunk entry point — assembles config, engine, graph, and sessions into a single app object.

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

### DeFunk

**File**: `src/de_funk/app.py:31`

**Purpose**: Top-level application object. Assembles everything from config.

| Method | Description |
|--------|-------------|
| `from_config(connection_type: str, log_level: str) -> DeFunk` | Create a fully wired DeFunk app from config files. |
| `from_app_config() -> DeFunk` | Create DeFunk from an already-loaded AppConfig. |
| `build_session()` | Create a BuildSession for building Silver tables. |
| `query_session()` | Create a QuerySession for interactive queries. |
| `ingest_session()` | Create an IngestSession for data ingestion. |

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
| `src/de_funk/app.py` | DeFunk — Top-level application class. | `DeFunk` |
