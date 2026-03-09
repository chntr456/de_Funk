# Proposal 015: Domain Model v4 Implementation

## Context

The `domains_testing/` directory (168 markdown files) defines a complete domain model specification with 4 file types, multi-level inheritance, federation, views, subsets, and multi-phase builds. The current production `domains/` (19 files) uses a simpler single-file-per-model pattern loaded by `ModelConfigLoader` (745 lines). The Python loader and builder must be extended to support ALL mechanisms in `domains_testing/`, then the directory renamed to replace `domains/`.

**Branch**: `claude/domain-testing-structure`
**Proposal file**: `docs/proposals/015-domain-model-v4-implementation.md`

---

## Architecture Decisions

### 1. New loader class, not rewrite
The existing `ModelConfigLoader` works for the current `domains/`. A new `DomainConfigLoaderV4` class handles the multi-file format. A factory function auto-detects which format is in use based on directory structure (presence of `_model_guides_/` or `models/` subdirectory).

### 2. Composition — split into focused modules
Instead of growing `domain_loader.py` past 745 lines, new functionality splits into focused modules under `src/de_funk/config/domain/`:

```
src/de_funk/config/domain/
├── __init__.py              # DomainConfigLoaderV4 main class + factory
├── extends.py               # Extends resolution, deep_merge (extracted from current)
├── schema.py                # canonical_fields, additional_schema, derivations
├── subsets.py               # Subset auto-absorption
├── sources.py               # Source file processing, aliases, transforms
├── views.py                 # View assembly (derived, rollup, assumptions)
└── federation.py            # Federation children, union_of resolution
```

### 3. Build pipeline extensions — same composition pattern
New modules slot alongside existing `GraphBuilder`:

```
src/de_funk/models/base/
├── phase_builder.py         # Phased build orchestration
├── view_builder.py          # Derived + rollup view materialization
├── federation_builder.py    # Cross-model UNION creation
└── enrich_builder.py        # Post-build enrichment joins
```

### 4. File size limits enforced
No new file exceeds 350 lines. Existing files (`model.py` at 820, `domain_loader.py` at 745) get thin delegation points added, not expanded.

### 5. Backwards compatible
Existing `domains/` keeps working throughout. Migration (Phase 8) is a single rename operation.

---

## Phase 0: Proposal Document + Test Infrastructure

**Goal**: Write the formal proposal document and set up test fixtures that mirror `domains_testing/` structure.

### Files to Create
- `docs/proposals/015-domain-model-v4-implementation.md` — formal proposal (this plan's content, formatted for the proposals dir)
- `tests/unit/test_domain_v4_loader.py` — test file with fixtures for all phases
- `tests/fixtures/domain_v4/` — mini replica of `domains_testing/` for tests:
  - `_base/simple/base_template.md` (domain-base with canonical_fields, tables, auto_edges)
  - `_base/simple/subset_child.md` (subset_of with canonical_fields)
  - `models/test_model/model.md` (domain-model with extends, graph, build, measures)
  - `models/test_model/tables/dim_test.md` (domain-model-table with extends, additional_schema)
  - `models/test_model/tables/fact_test.md` (domain-model-table with derivations)
  - `models/test_model/sources/provider/source_a.md` (domain-model-source with aliases)
  - `models/test_model/views/view_test.md` (domain-model-view with assumptions)

### Mechanisms Enabled
None yet — infrastructure only.

### Tests
- Fixture validation: all test markdown files parse correctly
- File type detection: each fixture returns correct `type:` value

### Estimated Impact
- ~3 new files, ~200 lines of fixtures + 100 lines of proposal

---

## Phase 1: Core Loader — Multi-File Discovery

**Goal**: `DomainConfigLoaderV4` discovers and assembles multi-file models.

### What It Enables
- `type:` field discrimination (domain-base, domain-model, domain-model-table, domain-model-source, domain-model-view, reference)
- Auto-discovery of `tables/*.md`, `sources/**/*.md`, `views/*.md` within a model directory
- Assembly: discovered files merged into model config under `tables:`, `sources:`, `views:` keys
- `extends:` on individual table files (e.g., `extends: _base.property.parcel._dim_parcel`)
- Factory function: `get_domain_loader(domains_dir)` returns V3 or V4 loader based on directory structure

### Files to Create
- `src/de_funk/config/domain/__init__.py` (~250 lines) — `DomainConfigLoaderV4` class:
  - `_build_index()` — scan all `.md` files, categorize by `type:`
  - `load_model_config(model_name)` — primary API
  - `_discover_model_files(model_dir)` — find tables/, sources/, views/
  - `_assemble_model(model_config, tables, sources, views)` — merge into unified config
- `src/de_funk/config/domain/extends.py` (~200 lines) — extracted from current loader:
  - `resolve_extends(ref, domains_dir)` — dot notation resolution
  - `resolve_nested_extends(config)` — recursive section resolution
  - `deep_merge(base, override)` — dict merging

### Files to Modify
- `src/de_funk/config/domain_loader.py` — add `get_domain_loader()` factory at bottom (~15 lines)

### Dependencies
- Phase 0 (test fixtures)

### Tests (~15 tests)
- `test_build_index_discovers_all_types` — 4 file types indexed correctly
- `test_load_model_assembles_tables` — tables/*.md merged into config.tables
- `test_load_model_assembles_sources` — sources/**/*.md merged into config.sources
- `test_load_model_assembles_views` — views/*.md merged into config.views
- `test_extends_on_table_file` — table with `extends:` inherits base schema
- `test_extends_dot_notation` — `_base.property.parcel._dim_parcel` resolves
- `test_factory_detects_v4` — `get_domain_loader()` returns V4 for domains_testing/
- `test_factory_detects_v3` — `get_domain_loader()` returns V3 for domains/
- `test_deep_merge_dicts` — recursive merge semantics
- `test_deep_merge_lists_replaced` — lists override, not append

### Estimated Impact
- 3 new files (~500 lines), 1 modified file (~15 lines)

---

## Phase 2: Schema Mechanisms

**Goal**: Process canonical_fields, additional_schema, derivations, and subset auto-absorption.

### What It Enables
- `canonical_fields:` on base templates — semantic field definitions with `[name, type, nullable:, description:]`
- `additional_schema:` on table files — extra columns merged after inherited schema
- `derivations:` on table files — flat map overriding `{derived:}` on inherited columns
- Subset auto-absorption: child templates with `subset_of:` have `canonical_fields` + `measures` absorbed into parent's `subsets.target_table` as nullable columns with `{subset: VALUE}`

### Files to Create
- `src/de_funk/config/domain/schema.py` (~250 lines):
  - `process_canonical_fields(base_config)` — convert canonical_fields to schema entries
  - `merge_additional_schema(base_schema, additional)` — append additional columns
  - `apply_derivations(schema, derivations_map)` — override derived expressions
- `src/de_funk/config/domain/subsets.py` (~200 lines):
  - `absorb_subsets(parent_config, all_bases, domains_dir)` — scan for `subset_of:` children
  - `_find_subset_children(parent_ref, all_bases)` — discover children by `subset_of` value
  - `_absorb_fields(target_schema, child_fields, subset_value)` — add nullable columns with `{subset:}`
  - `_absorb_measures(target_measures, child_measures)` — merge child measures

### Files to Modify
- `src/de_funk/config/domain/__init__.py` — call schema + subset processing in `_assemble_model()`

### Dependencies
- Phase 1 (core loader provides assembled config)

### Tests (~12 tests)
- `test_canonical_fields_to_schema` — converts canonical_fields format to schema array
- `test_additional_schema_appended` — extra columns added after inherited
- `test_derivations_override_derived` — `derivations: {col: "expr"}` updates matching column's `{derived:}`
- `test_derivations_missing_column_ignored` — derivation for nonexistent column is safe no-op
- `test_subset_absorption_discovers_children` — finds residential/commercial/industrial by `subset_of`
- `test_subset_absorption_adds_nullable_columns` — absorbed columns are nullable with `{subset: VALUE}`
- `test_subset_absorption_merges_measures` — child measures appear on parent
- `test_subset_target_table` — columns added to correct table (not all tables)
- `test_wide_table_pattern` — full parcel + residential + commercial integration

### Estimated Impact
- 2 new files (~450 lines), 1 modified file (~20 lines)

---

## Phase 3: Source Mechanisms

**Goal**: Process source files — aliases, transforms, discriminators, multi-source union.

### What It Enables
- `aliases:` — `[[canonical, expression], ...]` → SELECT expression list for Bronze→Silver
- `maps_to:` — which model table this source populates
- `domain_source:` — literal column injected into every row
- `entry_type:` / `event_type:` — discriminator literals injected
- `transform: unpivot` + `unpivot_aliases:` — wide-to-long transformation
- `transform: aggregate` + `group_by:` — source-level aggregation
- Multi-source union: sources with same `maps_to:` auto-grouped and UNIONed
- `sources_from:` directory auto-discovery

### Files to Create
- `src/de_funk/config/domain/sources.py` (~300 lines):
  - `process_sources(source_configs, model_config)` — group by maps_to, validate aliases
  - `build_select_expressions(aliases)` — convert alias pairs to SQL SELECT list
  - `build_unpivot_plan(source_config)` — generate unpivot transformation spec
  - `group_sources_by_target(sources)` — group sources by maps_to for UNION

### Files to Modify
- `src/de_funk/config/domain/__init__.py` — call source processing in assembly
- `src/de_funk/models/base/graph_builder.py` — add `_load_from_sources()` method that reads source config and applies aliases/transforms instead of raw bronze read (~50 lines added)

### Dependencies
- Phase 1 (source file discovery)

### Tests (~10 tests)
- `test_aliases_to_select_list` — alias pairs become SQL expressions
- `test_domain_source_injected` — literal column added to SELECT
- `test_entry_type_injected` — discriminator column added
- `test_multi_source_grouped` — two sources with same maps_to grouped
- `test_unpivot_plan_generated` — unpivot config produces correct column mapping
- `test_sources_from_directory` — discovers all source files in directory tree
- `test_source_extends_base` — source file's `extends:` resolves to base template

### Estimated Impact
- 1 new file (~300 lines), 2 modified files (~70 lines added)

---

## Phase 4: Build Mechanisms

**Goal**: Phased builds, enrichment, generated tables, seed data, intermediate tables.

### What It Enables
- `build.phases:` — ordered materialization: `{1: {tables: [dim_x], persist: true}, 2: {tables: [dim_y], enrich: true}}`
- `enrich:` on tables — post-build joins adding aggregate columns to dimensions
- `generated: true` — tables computed from Silver data (e.g., `fact_stock_technicals`)
- `static: true` / `seed: true` + `data:` — inline seed rows for reference dimensions
- `persist: false` — intermediate tables that exist in memory only
- Phase-aware build: dims first, then enriched dims, then facts

### Files to Create
- `src/de_funk/models/base/phase_builder.py` (~300 lines):
  - `PhasedBuilder(model_config, graph_builder)` — orchestrates multi-phase build
  - `build_phase(phase_num, phase_config)` — builds tables for one phase
  - `_build_seed_table(table_config)` — creates DataFrame from inline `data:` block
  - `_build_generated_table(table_config)` — runs post-build generation
  - `_apply_enrichment(dim_df, enrich_config)` — joins aggregate columns onto dimension
  - `_handle_persistence(table_name, df, persist)` — write or hold in memory

### Files to Modify
- `src/de_funk/models/base/model.py` — add `PhasedBuilder` delegation in `build()` method (~20 lines)
- `src/de_funk/models/base/graph_builder.py` — support `generated: true` and `static: true` node types (~30 lines)

### Dependencies
- Phase 3 (source loading provides input DataFrames to phases)

### Tests (~12 tests)
- `test_phases_ordered_correctly` — phase 1 tables built before phase 2
- `test_seed_table_from_data` — inline data block becomes DataFrame
- `test_enrich_adds_aggregate_columns` — dimension gains columns from fact aggregation
- `test_generated_table_built_from_silver` — generated table reads from Silver not Bronze
- `test_persist_false_not_written` — intermediate tables stay in memory
- `test_phase_with_enrich_flag` — enrichment only runs in phases with `enrich: true`

### Estimated Impact
- 1 new file (~300 lines), 2 modified files (~50 lines added)

---

## Phase 5: View Mechanisms

**Goal**: Materialize derived and rollup views.

### What It Enables
- `type: derived` views — join dimension data, apply assumptions, compute new columns
- `type: rollup` views — GROUP BY to coarser grain, aggregate columns
- `assumptions:` — named typed parameters with `source:` binding and `join_on:` spec
- `{derived: "expression"}` on view schema columns — computed output columns
- View layering — views reference other views in `from:`, dependency chain resolved automatically
- Model-level view overrides — `views.view_name.assumptions:` in model.md

### Files to Create
- `src/de_funk/models/base/view_builder.py` (~300 lines):
  - `ViewBuilder(model_config, table_registry)` — resolves view dependency chain
  - `build_derived_view(view_config)` — join + assumptions + derived columns
  - `build_rollup_view(view_config)` — GROUP BY + aggregations
  - `_resolve_assumptions(assumptions, table_registry)` — bind assumption values from dimension tables
  - `_resolve_view_chain(views)` — topological sort of view dependencies
- `src/de_funk/config/domain/views.py` (~150 lines):
  - `assemble_views(model_views, base_views)` — merge model overrides onto base view templates
  - `resolve_view_extends(view_config, bases)` — apply base view + override assumptions

### Files to Modify
- `src/de_funk/models/base/model.py` — add `ViewBuilder` delegation after `build()` (~15 lines)
- `src/de_funk/models/base/model_writer.py` — support `views/` output directory alongside `dims/` and `facts/` (~10 lines)

### Dependencies
- Phase 4 (views reference tables built in earlier phases)

### Tests (~10 tests)
- `test_derived_view_joins_assumption` — equalization_factor joined from dim_tax_district
- `test_derived_view_computed_column` — `assessed_value_total * equalization_factor` computed
- `test_rollup_view_changes_grain` — parcel-level → township-level aggregation
- `test_view_layering` — view_estimated_tax reads from view_equalized_values
- `test_assumption_override` — model-level assumption binding replaces base default
- `test_view_measures` — measures on view columns calculate correctly
- `test_views_written_to_silver` — views persisted at `{root}/views/{view_name}/`

### Estimated Impact
- 2 new files (~450 lines), 2 modified files (~25 lines added)

---

## Phase 6: Federation Mechanisms

**Goal**: Cross-model UNION tables and federation discovery.

### What It Enables
- `federation.enabled: true` + `federation.union_key:` — signals a base participates in federation
- `federation.children:` on base templates — lists implementing models
- `union_of:` on federation model tables — `[municipal_finance.fact_ledger_entries, corporate_finance.fact_ledger_entries]`
- Federation models (`models/_base/accounting_federation/model.md`) that union child model tables
- Schema inheritance for union tables (`schema: inherited` → infer from children)

### Files to Create
- `src/de_funk/models/base/federation_builder.py` (~250 lines):
  - `FederationBuilder(model_config, session)` — resolves and unions child tables
  - `build_union_table(table_name, union_of_refs)` — UNION ALL from child model tables
  - `_load_child_table(model_name, table_name)` — load from Silver via session
  - `_align_schemas(dataframes)` — ensure all children have same columns (fill nulls)
  - `_inject_union_key(df, source_value)` — add `domain_source` column
- `src/de_funk/config/domain/federation.py` (~150 lines):
  - `resolve_federation(model_config, all_configs)` — resolve children references
  - `validate_union_schemas(union_refs, all_configs)` — verify schema compatibility

### Files to Modify
- `src/de_funk/models/base/model.py` — add `FederationBuilder` delegation (~15 lines)

### Dependencies
- Phase 4 (child models must be built first; federation models depend on children via `depends_on`)

### Tests (~8 tests)
- `test_union_of_two_tables` — two fact tables UNIONed with aligned schemas
- `test_union_key_injected` — `domain_source` column added to each child
- `test_schema_alignment_fills_nulls` — missing columns in one child filled with null
- `test_federation_children_resolved` — children list maps to real model configs
- `test_federation_depends_on` — federation model's depends_on includes all children

### Estimated Impact
- 2 new files (~400 lines), 1 modified file (~15 lines)

---

## Phase 7: Graph Mechanisms

**Goal**: auto_edges from base templates, optional edges, named paths.

### What It Enables
- `auto_edges:` on base templates — FK patterns auto-applied to all fact tables matching schema columns
- `optional: true` on edges — generates LEFT JOIN instead of INNER JOIN for nullable FKs
- `graph.paths:` — named multi-hop traversals: `{steps: [{from: A, to: B, via: col}, ...]}`
- Path resolution at query time — `session.traverse_path("assessment_to_tax_district")`

### Files to Create
- `src/de_funk/models/base/auto_edge_resolver.py` (~200 lines):
  - `resolve_auto_edges(model_config, base_configs)` — walk inheritance chain, collect auto_edges
  - `_match_auto_edges_to_tables(auto_edges, tables)` — check which fact tables have matching FK columns
  - `_expand_auto_edge(edge_template, table_name)` — instantiate concrete edge from template
  - `resolve_paths(path_configs, edges)` — validate path steps against known edges

### Files to Modify
- `src/de_funk/models/base/graph_builder.py` — respect `optional: true` → LEFT JOIN (~15 lines)
- `src/de_funk/config/domain/__init__.py` — call auto_edge resolution during assembly (~10 lines)
- `src/de_funk/models/api/session.py` — add `traverse_path()` method (~30 lines)

### Dependencies
- Phase 1 (extends chain must be resolved to collect auto_edges from parents)

### Tests (~8 tests)
- `test_auto_edges_from_base` — base template's auto_edges appear on child model's facts
- `test_auto_edge_only_if_column_exists` — auto_edge skipped if fact table lacks FK column
- `test_optional_edge_left_join` — `optional: true` edge generates LEFT JOIN
- `test_path_validation` — path steps reference valid edges
- `test_path_traversal` — multi-hop path produces correct join chain

### Estimated Impact
- 1 new file (~200 lines), 3 modified files (~55 lines added)

---

## Phase 8: Migration — domains_testing → domains

**Goal**: Replace production `domains/` with `domains_testing/`.

### Steps
1. Rename `domains/` → `domains_v3_archive/`
2. Rename `domains_testing/` → `domains/`
3. Update `domain_loader.py` factory — V4 loader becomes default
4. Update any hardcoded `domains_testing` references in tests
5. Run full integration test against all 168 files
6. Update CLAUDE.md directory structure section

### Files to Modify
- `src/de_funk/config/domain_loader.py` — update factory default
- `tests/` — update any path references
- `CLAUDE.md` — update directory structure documentation
- `.gitignore` — if any relevant entries

### Dependencies
- All previous phases (1-7)

### Tests
- `test_all_168_files_parse` — every .md file in new domains/ loads without error
- `test_build_order_resolves` — topological sort succeeds for all models
- `test_cross_model_extends` — cross-domain extends references resolve

### Estimated Impact
- Directory rename + ~4 modified files

---

## Summary Statistics

| Phase | New Files | Modified Files | New Lines | Tests |
|-------|-----------|---------------|-----------|-------|
| 0: Infrastructure | 3+ | 0 | ~300 | 2 |
| 1: Core Loader | 3 | 1 | ~500 | 15 |
| 2: Schema | 2 | 1 | ~450 | 12 |
| 3: Sources | 1 | 2 | ~370 | 10 |
| 4: Build | 1 | 2 | ~350 | 12 |
| 5: Views | 2 | 2 | ~475 | 10 |
| 6: Federation | 2 | 1 | ~415 | 8 |
| 7: Graph | 1 | 3 | ~255 | 8 |
| 8: Migration | 0 | 4 | ~50 | 3 |
| **Total** | **~15** | **~16** | **~3,165** | **~80** |

---

## Verification Plan

After each phase, run:
```bash
# Unit tests for that phase
pytest tests/unit/test_domain_v4_loader.py -v -k "phase_N"

# After Phase 8 (migration), full integration:
pytest tests/unit/test_domain_v4_loader.py -v          # All unit tests
pytest tests/integration/ -v                            # Integration suite
python -c "
from de_funk.config.domain import get_domain_loader
loader = get_domain_loader(Path('domains'))
for model in loader.list_models():
    config = loader.load_model_config(model)
    print(f'{model}: {len(config.get(\"tables\", {}))} tables, {len(config.get(\"sources\", {}))} sources')
"
```

Final validation:
- All 168 markdown files parse without errors
- Build order resolves for all models (no circular deps)
- Every `extends:` reference resolves to a real file
- Every `maps_to:` target matches a known table
- Every `fk:` reference points to a real table.column
- Subset auto-absorption produces correct nullable columns on dim_parcel

---

## Critical Files Reference

| File | Lines | Role |
|------|-------|------|
| `src/de_funk/config/domain_loader.py` | 745 | Current V3 loader — add factory function |
| `src/de_funk/models/base/builder.py` | 557 | Abstract builder — not modified directly |
| `src/de_funk/models/base/model.py` | 820 | BaseModel — thin delegation to new builders |
| `src/de_funk/models/base/graph_builder.py` | 647 | Graph/node building — source loading + optional edges |
| `src/de_funk/models/base/model_writer.py` | 314 | Silver persistence — add views/ output |
| `src/de_funk/models/api/session.py` | 150+ | Query interface — add path traversal |
| `domains_testing/_base/property/parcel.md` | — | Most complex base (subsets, views, auto_edges) |
| `domains_testing/models/municipal/finance/model.md` | — | Most complex model (multi-source, federation) |
