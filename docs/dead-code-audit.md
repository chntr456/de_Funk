# Dead Code Audit

**Date**: 2026-03-19

## Summary

24 dead items found across 4 categories. Most are remnants from Streamlit removal and v2.6 domain reorganization.

---

## Critical — Dead Imports (runtime errors)

| File | Line | Import | Issue |
|------|------|--------|-------|
| `scripts/debug/test_ui_model_access.py` | 86 | `from de_funk.notebook.managers import NotebookManager` | Module deleted |
| `tests/diagnose_stocks_tab.py` | 361 | `from de_funk.notebook.exhibits.registry import ExhibitTypeRegistry` | Module deleted |

## Completely Dead Files

| File | Contents | Lines |
|------|----------|-------|
| `src/de_funk/notebook/folder_context.py` | `FolderFilterContext`, `FolderFilterContextManager` | 254 |
| `src/de_funk/models/api/services.py` | Empty compat layer (`__all__ = []`) | ~15 |
| `src/de_funk/models/api/types.py` | Empty compat layer (`__all__ = []`) | ~15 |

## Dead Classes in Active Modules

### `src/de_funk/notebook/schema.py` — Old Streamlit GreatTable config
| Class | Line |
|-------|------|
| `GTColumnConfig` | 515 |
| `GTDateDimensionConfig` | 547 |
| `GTFootnoteConfig` | 558 |
| `GTRowConfig` | 535 |
| `GTSpannerConfig` | 527 |
| `GreatTableConfig` | 566 |
| `WeightingMethod` | 47 |
| `WeightingConfig` | 476 |

### `src/de_funk/notebook/parsers/`
| Class/Function | File | Line |
|---------------|------|------|
| `BlockPosition` | `markdown_parser.py` | 51 |
| `MarkdownNotebook` | `markdown_parser.py` | 59 |
| `VariableResolver` | `yaml_parser.py` | 450 |

### `src/de_funk/notebook/expressions/resolver.py`
| Function | Line |
|----------|------|
| `resolve_expression()` | 326 |

## Dead Functions in Utils

### `src/de_funk/utils/env_loader.py` — replaced by `inject_credentials_into_config()`
- `find_dotenv()`
- `get_api_keys()`
- `get_bls_api_keys()`
- `get_chicago_api_keys()`
- `get_polygon_api_keys()`

### `src/de_funk/utils/repo.py`
- `repo_root_for_script()`

## Empty Directories
- `src/de_funk/pipelines/facets/` — no implementations

---

## Load-Bearing (do NOT remove)

All of `models/api/` except `services.py` and `types.py` — see [Proposal 016](proposals/016-api-consolidation.md) for migration plan.

All of `notebook/` except items listed above — parsers, filters, expressions, schema are still imported by tests and notebook session code.
