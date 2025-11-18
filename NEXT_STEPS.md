# Next Steps for Model Architecture Redesign

**Last Updated**: 2025-11-18
**Status**: Phase 1 & 2 Complete (~60% done)
**Current Branch**: `claude/redesign-yaml-models-01MLMLiFdF3ivuevj8Yuku2Q`

---

## 🎯 What's Been Completed

### ✅ Phase 1: Base Infrastructure (COMPLETE)
- [x] Base securities templates (`_base/securities/` with schema, graph, measures)
- [x] ModelConfigLoader with YAML inheritance (`config/model_loader.py`)
- [x] Company model (modular structure)
- [x] Stocks model (complete with Python measures)
- [x] Skeleton models for Options, ETFs, Futures
- [x] Comprehensive documentation (`IMPLEMENTATION_SUMMARY.md`)

### ✅ Phase 2: Core Integration (COMPLETE)
- [x] BaseModel Python measures support
- [x] Model registry updated for modular YAMLs
- [x] Test script created and verified (`scripts/test_modular_architecture.py`)
- [x] Architecture tested and working

### 📊 Test Results
```
✅ ModelConfigLoader loads modular YAMLs
✅ YAML inheritance resolves correctly
✅ Stocks inherited 100% of base security fields/measures
✅ Model registry discovers modular models
✅ Model classes auto-register correctly
```

---

## 🚧 What Remains To Be Done

### Phase 3: Bronze Layer Updates (HIGH PRIORITY)

**Why:** New models need unified bronze tables with asset_type filtering.

**Tasks:**
1. **Create SecuritiesReferenceFacet**
   - File: `datapipelines/providers/polygon/facets/securities_reference_facet.py`
   - Purpose: Normalize ticker reference data with CIK extraction
   - Schema: All securities with asset_type classification

2. **Create SecuritiesPricesFacet**
   - File: `datapipelines/providers/polygon/facets/securities_prices_facet.py`
   - Purpose: Unified daily prices for all asset types
   - Schema: OHLCV with asset_type column

3. **Update Polygon endpoints config**
   - File: `configs/polygon_endpoints.json`
   - Add: `include_cik=true` to reference data endpoints
   - Add: Options Greeks endpoint

4. **Create OptionsGreeksFacet** (future)
   - File: `datapipelines/providers/polygon/facets/options_greeks_facet.py`
   - Purpose: Normalize options Greeks data

**Estimated Effort:** 4-6 hours

---

### Phase 4: Complete Remaining Models (MEDIUM PRIORITY)

**Why:** Options, ETFs, Futures are currently skeleton-only.

**Tasks:**

**1. Options Model**
- Create `configs/models/options/schema.yaml` ✅ (already created)
- Create `configs/models/options/graph.yaml` ✅ (already created)
- Complete `configs/models/options/measures.yaml` ✅ (already created)
- Create `models/implemented/options/model.py`
- Create `models/implemented/options/measures.py` (Black-Scholes, Greeks)
- Create `models/implemented/options/__init__.py`

**2. ETFs Model**
- Create `configs/models/etfs/schema.yaml`
- Create `configs/models/etfs/graph.yaml`
- Create `configs/models/etfs/measures.yaml`
- Create `models/implemented/etfs/model.py`
- Create `models/implemented/etfs/measures.py` (holdings-weighted calculations)
- Create `models/implemented/etfs/__init__.py`

**3. Futures Model**
- Create `configs/models/futures/schema.yaml`
- Create `configs/models/futures/graph.yaml`
- Create `configs/models/futures/measures.yaml`
- Create `models/implemented/futures/model.py`
- Create `models/implemented/futures/measures.py` (roll-adjusted, continuous)
- Create `models/implemented/futures/__init__.py`

**Estimated Effort:** 6-8 hours

---

### Phase 5: Update Scripts (MEDIUM PRIORITY)

**Why:** Existing scripts reference old model names (equity, corporate).

**Impacted Scripts (from scan):**
```bash
scripts/
├── build_all_models.py           # May reference old models
├── rebuild_model.py              # Needs to support modular models
├── test_all_models.py            # Update model list
├── test_domain_model_integration_duckdb.py  # Update model references
├── test_domain_model_integration_spark.py   # Update model references
└── run_full_pipeline.py          # May need updates
```

**Tasks:**
1. **Audit scripts** - Identify all references to `equity`, `corporate`
2. **Update model references** - Replace with `stocks`, `company`
3. **Test script execution** - Verify scripts run without errors
4. **Update script documentation** - Reflect new model names

**Estimated Effort:** 3-4 hours

---

### Phase 6: Update Tests (MEDIUM PRIORITY)

**Why:** Tests may reference old models and schemas.

**Impacted Test Files (estimated):**
```bash
tests/
├── unit/
│   ├── test_measure_framework.py      # May need updates
│   └── test_backend_adapters.py       # Should work as-is
└── integration/
    └── test_measure_pipeline.py       # May need model updates
```

**Tasks:**
1. **Audit test files** - Check for hardcoded model names
2. **Update test fixtures** - Use new model structure
3. **Add new tests** - Test Python measures, modular loading
4. **Run test suite** - Verify all tests pass

**Estimated Effort:** 4-5 hours

---

### Phase 7: Update Examples (LOW PRIORITY)

**Why:** Examples demonstrate usage patterns, should reflect new architecture.

**Impacted Examples:**
```bash
examples/
├── measure_framework/
│   ├── 01_basic_usage.py             # Update model names
│   └── 02_troubleshooting.py         # Update model names
└── ...
```

**Tasks:**
1. **Audit examples** - Check model references
2. **Update code samples** - Use stocks/company instead of equity/corporate
3. **Add new examples** - Demonstrate Python measures
4. **Test examples** - Verify they run

**Estimated Effort:** 2-3 hours

---

### Phase 8: Create DuckDB Views (MEDIUM PRIORITY)

**Why:** User requested materialized views for DuckDB analytics.

**Tasks:**
1. **Create view definitions**
   - File: `configs/duckdb_views.yaml` or `configs/views/`
   - Define views for common queries

2. **Create view builder script**
   - File: `scripts/create_duckdb_views.py`
   - Read view definitions
   - Create views in DuckDB database

3. **Common views to create:**
   - `stocks_with_company` - Stocks joined with company data
   - `stocks_with_technicals` - Prices with technical indicators
   - `sector_performance` - Daily sector returns
   - `top_movers` - Top gainers/losers by day

4. **Test views**
   - Verify views are queryable
   - Test performance vs. ad-hoc joins

**Estimated Effort:** 3-4 hours

---

### Phase 9: Cleanup & Migration (HIGH PRIORITY)

**Why:** Remove old models to avoid confusion.

**Tasks:**
1. **Backup old models**
   ```bash
   mkdir -p archive/old_models_backup/
   cp configs/models/{equity,corporate}.yaml archive/old_models_backup/
   ```

2. **Remove old model configs**
   ```bash
   rm configs/models/equity.yaml
   rm configs/models/corporate.yaml
   ```

3. **Remove old model implementations**
   ```bash
   rm -rf models/implemented/equity/
   rm -rf models/implemented/corporate/
   ```

4. **Clean up old bronze tables** (if safe)
   ```bash
   # Only if new bronze structure is working!
   rm -rf storage/bronze/ref_ticker/
   rm -rf storage/bronze/ref_all_tickers/
   rm -rf storage/bronze/prices_daily/
   ```

5. **Update migration guide**
   - Create `docs/MIGRATION_GUIDE_V2.md`
   - Document old → new model mapping
   - Provide code examples for migration

**Estimated Effort:** 2-3 hours

---

### Phase 10: Documentation Updates (HIGH PRIORITY)

**Why:** Documentation must reflect new architecture.

**Files to Update:**

**1. CLAUDE.md** (primary AI assistant guide)
- Update repository structure section
- Document modular YAML architecture
- Update model list (stocks, company, options, etfs, futures)
- Add section on Python measures
- Update configuration system section

**2. QUICKSTART.md**
- Update model references
- Update example code to use new models

**3. TESTING_GUIDE.md**
- Add section on testing modular models
- Update model names in examples

**4. Create New Documentation**
- `docs/MEASURES_GUIDE.md` - When to use YAML vs. Python measures
- `docs/SECURITIES_ARCHITECTURE.md` - Inheritance diagram and design
- `docs/MIGRATION_GUIDE_V2.md` - How to migrate from v1 to v2

**Estimated Effort:** 4-5 hours

---

## 📋 Priority Matrix

| Priority | Phase | Effort | Blockers | Impact |
|----------|-------|--------|----------|--------|
| 🔴 HIGH | Phase 3: Bronze Layer | 4-6h | None | Models can't build without bronze data |
| 🔴 HIGH | Phase 9: Cleanup | 2-3h | Phase 3 | Removes confusion, prevents issues |
| 🔴 HIGH | Phase 10: Documentation | 4-5h | None | Critical for usability |
| 🟡 MEDIUM | Phase 4: Complete Models | 6-8h | Phase 3 | Enables full functionality |
| 🟡 MEDIUM | Phase 5: Update Scripts | 3-4h | None | Scripts may fail with old names |
| 🟡 MEDIUM | Phase 6: Update Tests | 4-5h | Phase 4 | Tests ensure quality |
| 🟡 MEDIUM | Phase 8: DuckDB Views | 3-4h | Phase 3 | Performance optimization |
| 🟢 LOW | Phase 7: Update Examples | 2-3h | None | Examples still work, just outdated |

**Total Estimated Effort:** 31-41 hours

---

## 🚀 Recommended Execution Order

### Week 1: Core Functionality
1. ✅ Phase 1: Base Infrastructure (DONE)
2. ✅ Phase 2: Core Integration (DONE)
3. Phase 3: Bronze Layer Updates (START HERE)
4. Phase 9: Cleanup & Migration

### Week 2: Complete Implementation
5. Phase 4: Complete Remaining Models (Options, ETFs, Futures)
6. Phase 5: Update Scripts
7. Phase 6: Update Tests

### Week 3: Polish & Documentation
8. Phase 8: Create DuckDB Views
9. Phase 10: Documentation Updates
10. Phase 7: Update Examples

---

## 🧪 Testing Checklist

Before considering the redesign complete, verify:

- [ ] All new models (stocks, company, options, etfs, futures) build successfully
- [ ] Cross-model queries work (stocks → company)
- [ ] Python measures execute correctly
- [ ] Model registry discovers all models
- [ ] YAML inheritance resolves without errors
- [ ] Both DuckDB and Spark backends work
- [ ] Old model references removed from scripts/tests
- [ ] Documentation is up-to-date
- [ ] Examples run without errors
- [ ] No regressions in existing functionality

---

## 🔧 Quick Commands Reference

### Test Architecture
```bash
# Run architecture verification
python -m scripts.test_modular_architecture

# Test specific model loading
python -c "from config.model_loader import ModelConfigLoader; from pathlib import Path; loader = ModelConfigLoader(Path('configs/models')); print(loader.load_model_config('stocks'))"
```

### Build Models
```bash
# Build single model (when bronze data ready)
python -m scripts.rebuild_model --model stocks

# Build all models
python -m scripts.build_all_models
```

### Test Models
```bash
# Test all models
python -m scripts.test_all_models

# Integration test (DuckDB)
python -m scripts.test_domain_model_integration_duckdb

# Integration test (Spark)
python -m scripts.test_domain_model_integration_spark
```

### Run Full Pipeline
```bash
# Ingest bronze + build silver
python run_full_pipeline.py --top-n 100
```

---

## 📞 Questions & Decision Points

### Q1: Should we keep backward compatibility with old model names?

**Current Status:** No backward compatibility implemented.

**Options:**
- **A)** Create aliases: `equity` → `stocks`, `corporate` → `company`
- **B)** Clean break: Force users to update code
- **C)** Deprecation period: Warn for 1 release, remove in next

**Recommendation:** Option B (clean break) since this is a redesign from scratch.

---

### Q2: How to handle existing bronze data?

**Current Status:** New bronze structure not implemented yet.

**Options:**
- **A)** Migrate existing data to new structure
- **B)** Keep both structures temporarily
- **C)** Fresh ingestion (delete old bronze)

**Recommendation:** Option C (fresh ingestion) if data volume is manageable.

---

### Q3: Should we implement all securities models now?

**Current Status:** Stocks complete, others skeleton.

**Options:**
- **A)** Complete all models before deployment
- **B)** Deploy stocks/company first, add others iteratively
- **C)** Wait for user feedback

**Recommendation:** Option B (iterative) to get feedback early.

---

## 📝 Notes for Future Development

### Performance Considerations
- Python measures may be slower than SQL for large datasets
- Consider caching Python measure results
- Monitor performance and optimize hot paths

### Scalability
- Modular YAML structure scales well to 50+ models
- Python measures scale to complex calculations
- Consider distributed computing for large Python measures

### Maintenance
- Keep base templates minimal and stable
- Document breaking changes in CHANGELOG
- Version model configs explicitly

---

**Status**: Ready for Phase 3 (Bronze Layer) or Phase 9 (Cleanup)
**Next Action**: Choose priority and begin implementation

**Last Updated**: 2025-11-18
