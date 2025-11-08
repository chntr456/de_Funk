# de_Funk TODO Tracker

This document consolidates all outstanding tasks, organized by priority and area. This is the central task tracking document for de_Funk development.

**Last Updated:** 2025-11-08

---

## Table of Contents

- [How to Use This Tracker](#how-to-use-this-tracker)
- [Priority Definitions](#priority-definitions)
- [Tasks by Area](#tasks-by-area)
  - [Critical Priority](#critical-priority)
  - [High Priority](#high-priority)
  - [Medium Priority](#medium-priority)
  - [Low Priority](#low-priority)
- [Task Summary](#task-summary)

---

## How to Use This Tracker

### Status Indicators
- **Not Started** - Task is planned but no work has begun
- **In Progress** - Currently being worked on
- **Blocked** - Waiting on dependency or external factor
- **Completed** - Task is done and verified
- **Deferred** - Lower priority, postponed to future release

### Updating Tasks
1. When starting work on a task, change status to "In Progress"
2. Add your name/initials to the assignee field
3. Update the last modified date
4. Move completed tasks to the "Completed" section at bottom of file

---

## Priority Definitions

| Priority | Description | Timeline |
|----------|-------------|----------|
| **Critical** | Blocks core functionality or has major architectural impact | This week |
| **High** | Important for user experience or system stability | This month |
| **Medium** | Valuable improvements but not urgent | This quarter |
| **Low** | Nice-to-have enhancements | Backlog |

---

## Tasks by Area

### Critical Priority

#### Data Pipeline

| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| DP-001 | Eliminate `company_silver_builder.py` | Not Started | - | Legacy code duplicates BaseModel functionality. Use `BaseModel.write_tables()` instead |
| DP-002 | Add retry logic to API ingestors | Not Started | - | Handle transient failures (network, rate limits) |
| DP-003 | Implement Bronze data validation | Not Started | - | Validate schema before writing to prevent corrupt data |

#### Models

| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| MOD-001 | Add comprehensive tests for `BaseModel.write_tables()` | Not Started | - | Test all write modes, partitioning, optimization |
| MOD-002 | Add write_tables() to forecast model | Not Started | - | Complete migration to new pattern |
| MOD-003 | Fix measure calculation edge cases | Not Started | - | Handle empty DataFrames, missing columns |

#### Architecture

| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| ARCH-001 | Document storage router path resolution | Not Started | - | Clarify how Bronze/Silver paths are resolved |
| ARCH-002 | Add logging framework | Not Started | - | Structured logging for debugging and monitoring |

---

### High Priority

#### Data Pipeline

| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| DP-004 | Add incremental ingestion support | Not Started | - | Only fetch new data (watermark-based) |
| DP-005 | Implement data quality checks | Not Started | - | Row counts, null checks, value ranges |
| DP-006 | Add facet unit tests | Not Started | - | Test normalization, postprocessing |
| DP-007 | Create provider template/generator | Not Started | - | Scaffold new providers quickly |

#### Models

| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| MOD-004 | Add caching for expensive measure calculations | Not Started | - | Avoid recomputing same metrics |
| MOD-005 | Support delta/append write modes | Not Started | - | Currently only overwrite is supported |
| MOD-006 | Add model validation on build | Not Started | - | Check for missing edges, invalid paths |
| MOD-007 | Implement cross-model joins | Not Started | - | Join tables from different models (e.g., company + macro) |

#### UI

| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| UI-001 | Add filter validation and error messages | Not Started | - | Better UX for invalid filter combinations |
| UI-002 | Improve chart performance for large datasets | Not Started | - | Pagination, aggregation, sampling |
| UI-003 | Add export functionality (CSV, Excel) | Not Started | - | Download filtered data from UI |
| UI-004 | Create dashboard builder UI | Not Started | - | Drag-and-drop notebook creation |

#### Performance

| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| PERF-001 | Benchmark DuckDB vs Spark for queries | Not Started | - | Quantify performance differences |
| PERF-002 | Optimize ParquetLoader coalesce logic | Not Started | - | Dynamic file sizing based on data volume |
| PERF-003 | Add query result caching | Not Started | - | Cache frequently-run queries |

---

### Medium Priority

#### Data Pipeline

| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| DP-008 | Add support for streaming ingestion | Not Started | - | Real-time data processing |
| DP-009 | Implement data lineage tracking | Not Started | - | Track data provenance through pipeline |
| DP-010 | Add Bronze → Bronze transformations | Not Started | - | Clean/dedupe before Silver |
| DP-011 | Support multiple API key rotation | Not Started | - | Better rate limit management |

#### Models

| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| MOD-008 | Add SQL query interface to models | Not Started | - | Run custom SQL on model tables |
| MOD-009 | Support custom UDFs in transforms | Not Started | - | User-defined transformations |
| MOD-010 | Add dimension slowly-changing dimensions (SCD) support | Not Started | - | Track historical changes |
| MOD-011 | Implement model versioning | Not Started | - | Multiple model versions side-by-side |

#### Testing

| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| TEST-001 | Add integration tests for full pipeline | Not Started | - | End-to-end testing |
| TEST-002 | Create test fixtures for models | Not Started | - | Reusable sample data |
| TEST-003 | Add property-based tests | Not Started | - | Hypothesis/QuickCheck style |
| TEST-004 | Implement contract tests for APIs | Not Started | - | Validate external API responses |

#### Documentation

| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| DOC-001 | Add API reference docs | Not Started | - | Auto-generate from docstrings |
| DOC-002 | Create video tutorials | Not Started | - | Screen recordings for key workflows |
| DOC-003 | Write troubleshooting guide | Not Started | - | Common errors and solutions |
| DOC-004 | Document performance tuning | Not Started | - | Best practices for large datasets |

---

### Low Priority

#### Data Pipeline

| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| DP-012 | Add support for Parquet metadata | Not Started | - | Column statistics, compression info |
| DP-013 | Implement Bronze compaction | Not Started | - | Merge small files periodically |
| DP-014 | Add data sampling utilities | Not Started | - | Quick exploratory analysis |

#### Models

| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| MOD-012 | Add model dependency graph visualization | Not Started | - | Show model relationships |
| MOD-013 | Support custom aggregation functions | Not Started | - | Beyond sum/avg/count |
| MOD-014 | Add model cost estimation | Not Started | - | Predict build time/resource usage |

#### UI

| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| UI-005 | Add dark mode support | Not Started | - | UI theme toggle |
| UI-006 | Implement collaborative features | Not Started | - | Share notebooks, comments |
| UI-007 | Add mobile-responsive design | Not Started | - | Better mobile experience |

#### Infrastructure

| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| INFRA-001 | Add Docker Compose setup | Not Started | - | Easy local development |
| INFRA-002 | Create CI/CD pipeline | Not Started | - | Automated testing and deployment |
| INFRA-003 | Add monitoring and alerting | Not Started | - | Health checks, error alerts |

---

## Task Summary

### By Priority
- **Critical:** 8 tasks
- **High:** 15 tasks
- **Medium:** 17 tasks
- **Low:** 10 tasks
- **Total:** 50 tasks

### By Area
- **Data Pipeline:** 14 tasks
- **Models:** 14 tasks
- **UI:** 7 tasks
- **Testing:** 4 tasks
- **Documentation:** 4 tasks
- **Performance:** 3 tasks
- **Architecture:** 2 tasks
- **Infrastructure:** 3 tasks

### By Status
- **Not Started:** 50 tasks
- **In Progress:** 0 tasks
- **Blocked:** 0 tasks
- **Completed:** 0 tasks

---

## Recently Completed

*(Tasks moved here once completed)*

| Task ID | Description | Completed Date | Notes |
|---------|-------------|----------------|-------|
| ARCH-003 | Implement BaseModel.write_tables() | 2024-11 | Generic persistence method for all models |
| DP-015 | Migrate company model to use BaseModel.write_tables() | 2024-11 | Eliminated custom builder |

---

## Quick Reference

### Related Documents
- [Roadmap](./roadmap.md) - High-level feature timeline
- [Architecture TODOs](./backlog/architecture-todos.md) - Detailed architecture tasks
- [Models TODOs](./backlog/models-todos.md) - Model-specific improvements
- [Getting Started TODOs](./backlog/getting-started-todos.md) - Documentation improvements

### Priority Focus
- **This Week:** Critical priority tasks (DP-001, MOD-001, ARCH-001)
- **This Month:** High priority tasks in Data Pipeline and Models
- **This Quarter:** Medium priority Testing and Documentation tasks

---

## Notes

- This tracker is reviewed and updated weekly
- New tasks should be added to the appropriate priority/area section
- For detailed implementation notes, see individual backlog documents
- Archive completed tasks monthly to keep tracker concise
