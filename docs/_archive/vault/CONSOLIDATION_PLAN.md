# Documentation Consolidation Plan

**Plan for consolidating redundant markdown files**

Date: 2025-11-16

---

## Current State

- **Root-level markdown files**: 15 files
- **docs/ markdown files**: 121 files
- **Total**: 136 markdown files

Many files contain overlapping or outdated information.

---

## Consolidation Strategy

### Files to Keep (Core Documentation)

**Root Level:**
- `CLAUDE.md` - AI assistant guide ✅ KEEP
- `QUICKSTART.md` - Getting started guide ✅ KEEP
- `RUNNING.md` - How to run application ✅ KEEP
- `TESTING_GUIDE.md` - Testing strategies ✅ KEEP (or consolidate into vault)
- `PIPELINE_GUIDE.md` - Pipeline workflows ✅ KEEP (or consolidate into vault)
- `FORECAST_README.md` - Forecasting documentation ✅ KEEP (or consolidate into vault)
- `MODEL_DEPENDENCY_ANALYSIS.md` - Model dependencies ✅ KEEP (or consolidate into vault)
- `MODEL_EDGES_REFERENCE.md` - Cross-model relationships ✅ KEEP (or consolidate into vault)

**Vault Structure:**
- `docs/vault/` - New comprehensive technical reference ✅ KEEP
- `docs/architecture-diagram.drawio` - Visual architecture ✅ KEEP

### Files to Remove (Redundant/Outdated)

**Root Level:**
- `CALENDAR_DIMENSION_GUIDE.md` - Duplicate of SHARED_CALENDAR_DIMENSION.md → REMOVE
- `SHARED_CALENDAR_DIMENSION.md` - Consolidate into vault → REMOVE after migration
- `FILTER_PUSHDOWN_FIX.md` - Session-specific, outdated → ARCHIVE
- `REBUILD_STORAGE.md` - Operational notes → ARCHIVE
- `TEST_APP_README.md` - Duplicate of RUNNING.md → REMOVE
- `VERIFY_TICKER_COUNT.md` - Debug file → REMOVE
- `debug_dimensional_selector_exchange.md` - Debug file → REMOVE

**docs/ Directory:**
- `docs/session_summary.md` - Session notes → ARCHIVE
- `docs/TESTING_GUIDE.md` - Duplicate of root TESTING_GUIDE.md → REMOVE
- `docs/DELTA_LAKE_*.md` - Delta Lake experiments → ARCHIVE (not used)
- `docs/MIGRATION_GUIDE.md` - Session-specific → ARCHIVE
- `docs/STREAMLIT_*.md` - Session-specific → ARCHIVE
- `docs/archive/session-notes/` - Already archived → KEEP AS IS
- `docs/archive/experimental/` - Already archived → KEEP AS IS

### Files to Consolidate Into Vault

These should be migrated to the vault structure:

1. **Testing Documentation**
   - `TESTING_GUIDE.md` → `docs/vault/07-testing/testing-guide.md`
   - `docs/backend_testing.md` → Merge into vault
   - `docs/PIPELINE_TESTING_GUIDE.md` → Merge into vault

2. **Model Documentation**
   - `MODEL_DEPENDENCY_ANALYSIS.md` → `docs/vault/02-graph-architecture/dependency-resolution.md`
   - `MODEL_EDGES_REFERENCE.md` → `docs/vault/02-graph-architecture/cross-model-references.md`
   - `SHARED_CALENDAR_DIMENSION.md` → `docs/vault/03-model-framework/calendar-dimension.md`

3. **Pipeline Documentation**
   - `PIPELINE_GUIDE.md` → `docs/vault/04-data-pipelines/pipeline-architecture.md`
   - Content already covers ingestors, facets, providers

4. **Forecast Documentation**
   - `FORECAST_README.md` → `docs/vault/08-forecasting/forecast-models.md`

5. **Configuration Documentation**
   - `docs/ENV_SETUP.md` → `docs/vault/06-configuration/environment-variables.md`
   - `docs/configuration.md` → `docs/vault/06-configuration/config-loader.md`

6. **Notebook Documentation**
   - `docs/markdown_notebook_spec.md` → `docs/vault/05-ui-system/notebook-system.md`

---

## Vault Structure (Final)

```
docs/vault/
├── README.md                          # Navigation hub ✅
├── CONSOLIDATION_PLAN.md              # This file ✅
├── 01-core-components/
│   ├── base-model.md                  # ✅ Complete
│   ├── universal-session.md           # TODO
│   ├── connection-system.md           # TODO
│   └── storage-router.md              # TODO
├── 02-graph-architecture/
│   ├── graph-overview.md              # ✅ Complete
│   ├── nodes-edges-paths.md           # TODO
│   ├── dependency-resolution.md       # TODO (from MODEL_DEPENDENCY_ANALYSIS.md)
│   └── cross-model-references.md      # TODO (from MODEL_EDGES_REFERENCE.md)
├── 03-model-framework/
│   ├── model-lifecycle.md             # TODO
│   ├── yaml-configuration.md          # TODO
│   ├── measure-framework.md           # TODO
│   ├── calendar-dimension.md          # TODO (from SHARED_CALENDAR_DIMENSION.md)
│   └── implemented-models.md          # TODO
├── 04-data-pipelines/
│   ├── pipeline-architecture.md       # TODO (from PIPELINE_GUIDE.md)
│   ├── facets-system.md               # TODO
│   ├── ingestors.md                   # TODO
│   └── providers.md                   # TODO
├── 05-ui-system/
│   ├── notebook-system.md             # TODO (from markdown_notebook_spec.md)
│   ├── filter-engine.md               # TODO
│   ├── exhibits.md                    # TODO
│   └── streamlit-app.md               # TODO
├── 06-configuration/
│   ├── config-loader.md               # TODO (from docs/configuration.md)
│   ├── environment-variables.md       # TODO (from docs/ENV_SETUP.md)
│   └── api-configs.md                 # TODO
├── 07-testing/
│   ├── testing-guide.md               # TODO (from TESTING_GUIDE.md)
│   ├── backend-testing.md             # TODO (from docs/backend_testing.md)
│   └── pipeline-testing.md            # TODO (from docs/PIPELINE_TESTING_GUIDE.md)
└── 08-forecasting/
    ├── forecast-models.md             # TODO (from FORECAST_README.md)
    └── model-training.md              # TODO
```

---

## Recommended Root Documentation (Final)

Keep these user-facing guides at root:

```
/CLAUDE.md                    # AI assistant guide
/QUICKSTART.md                # Getting started
/RUNNING.md                   # How to run
/README.md                    # Project overview (if exists)
/docs/vault/                  # Technical reference vault
/docs/architecture-diagram.drawio  # Visual architecture
/docs/archive/                # Historical/experimental docs
```

Everything else moves into vault or archive.

---

## Migration Steps

1. ✅ Create vault structure
2. ✅ Document BaseModel (comprehensive)
3. ✅ Document graph architecture (overview)
4. ⏳ Create remaining vault documents
5. ⏳ Remove redundant root files
6. ⏳ Remove redundant docs/ files
7. ⏳ Update draw.io diagram
8. ⏳ Update CLAUDE.md references
9. ⏳ Commit changes

---

## Files to Remove Immediately

**Root Level:**
```bash
rm debug_dimensional_selector_exchange.md
rm VERIFY_TICKER_COUNT.md
rm TEST_APP_README.md
rm CALENDAR_DIMENSION_GUIDE.md  # Duplicate
```

**docs/ Level:**
```bash
rm docs/TESTING_GUIDE.md  # Duplicate of root
rm docs/DELTA_LAKE_IMPLEMENTATION_PROPOSAL.md
rm docs/DELTA_LAKE_IMPLEMENTATION_SUMMARY.md
rm docs/DELTA_LAKE_USAGE_GUIDE.md
rm docs/STREAMLIT_REFACTORING_PLAN.md
rm docs/STREAMLIT_CHANGES_SUMMARY.md
```

---

## Files to Archive

Move to `docs/archive/`:
```bash
mv FILTER_PUSHDOWN_FIX.md docs/archive/
mv REBUILD_STORAGE.md docs/archive/
mv docs/session_summary.md docs/archive/
mv docs/MIGRATION_GUIDE.md docs/archive/
mv docs/IMPLEMENTATION_SUMMARY.md docs/archive/
```

---

## Next Steps

1. Create remaining vault documentation sections
2. Remove redundant files
3. Archive session-specific files
4. Update cross-references in CLAUDE.md
5. Update draw.io diagram with vault structure
