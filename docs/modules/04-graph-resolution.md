---
title: "Graph & Field Resolution"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/core/graph.py
  - src/de_funk/api/resolver.py
  - src/de_funk/api/bronze_resolver.py
---

# Graph & Field Resolution

> DomainGraph (BFS join paths), FieldResolver (domain.field → table.column), and BronzeResolver.

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

### DomainGraph

**File**: `src/de_funk/core/graph.py:22`

**Purpose**: Queryable graph of domain model relationships.

| Method | Description |
|--------|-------------|
| `find_join_path(src: str, dst: str, allowed_domains: set[str] | None) -> list[tuple[str, str, str]] | None` | BFS shortest join path from src table to dst table. |
| `reachable_domains(core_domains: set[str]) -> set[str]` | Get all domains reachable from the core set (transitive deps). |
| `neighbors(table_name: str) -> list[str]` | Get adjacent tables. |
| `domains_for_table(table_name: str) -> str | None` | Get the domain that owns a table. |
| `all_tables() -> list[str]` | Get all tables in the graph. |
| `all_edges() -> list[tuple[str, str, str, str]]` | Get all edges as (from, to, col_a, col_b) tuples. |
| `distance(table_a: str, table_b: str) -> int` | Hop count between two tables (-1 if unreachable). |
| `connected_components() -> list[set[str]]` | Find connected components in the graph. |
| `subgraph(domains: set[str]) -> DomainGraph` | Create a scoped subgraph containing only the specified domains. |

### FieldRef

**File**: `src/de_funk/api/resolver.py:37`

**Purpose**: Parsed domain.field reference (e.g. 'corporate.finance.amount').

| Attribute | Type |
|-----------|------|
| `_known_domains` | `set[str]` |

### ResolvedField

**File**: `src/de_funk/api/resolver.py:81`

**Purpose**: Resolution result — storage path + column for a domain.field ref.

| Method | Description |
|--------|-------------|
| `domain() -> str` | Canonical domain name (e.g. 'corporate.finance'). |

### FieldResolver

**File**: `src/de_funk/api/resolver.py:107`

**Purpose**: Resolves domain.field references to Silver table paths.

| Method | Description |
|--------|-------------|
| `reachable_domains(core_domains: set[str]) -> set[str]` | Compute allowed domains: core domains + their depends_on. |
| `find_join_path(src: str, dst: str, allowed_domains: set[str] | None) -> list[tuple[str, str, str]] | None` | Find a join path between two Silver tables using BFS over graph.edges. |
| `resolve(ref_str: str) -> ResolvedField` | Resolve a domain.field string to a ResolvedField. |
| `resolve_many(refs: list[str]) -> dict[str, ResolvedField]` | <!-- TODO --> |
| `get_field_catalog() -> dict[str, dict]` | Return full field catalog — used by GET /api/domains. |

### BronzeEndpointInfo

**File**: `src/de_funk/api/bronze_resolver.py:40`

**Purpose**: Metadata for one Bronze endpoint table.

| Attribute | Type |
|-----------|------|
| `provider_id` | `str` |
| `endpoint_id` | `str` |
| `bronze_path` | `Path` |
| `fields` | `dict[str, str]` |

### BronzeResolver

**File**: `src/de_funk/api/bronze_resolver.py:48`

**Purpose**: Resolves provider.endpoint.field references to Bronze Delta Lake paths.

| Method | Description |
|--------|-------------|
| `resolve(ref_str: str) -> ResolvedField` | Resolve a provider.endpoint.field string to a ResolvedField. |
| `reachable_domains(core_domains: set[str]) -> set[str]` | Pass-through — Bronze has no domain scoping. |
| `find_join_path(src: str, dst: str, allowed_domains: set[str] | None) -> None` | Always returns None — Bronze has no join graph. |
| `get_endpoint_catalog() -> dict[str, dict]` | Return full Bronze endpoint catalog — used by GET /api/bronze/endpoints. |

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
| `src/de_funk/core/graph.py` | DomainGraph — queryable graph model built from EdgeSpec. | `DomainGraph` |
| `src/de_funk/api/resolver.py` | Field resolver — translates domain.field references to Silver table paths and columns. | `FieldRef`, `ResolvedField`, `FieldResolver` |
| `src/de_funk/api/bronze_resolver.py` | Bronze resolver — translates provider.endpoint.field references to Bronze table paths. | `BronzeEndpointInfo`, `BronzeResolver` |
