# Streamlit Backend Changes Summary

**Quick Reference Guide** | Created: 2025-11-12

---

## 📋 TL;DR

The Streamlit app currently queries **materialized views** for weighted aggregates.
We need to update it to use the **unified measure framework** instead.

**Impact:** 3 files, ~50-100 lines of code, ~2 hours work

---

## 🎯 Files That Need Changes

### 1. `app/notebook/api/notebook_session.py` 🔴 CRITICAL

**What:** Update `_get_weighted_aggregate_data()` method (lines 345-448)

**Change:**
```python
# OLD: Query materialized views
sql = f"SELECT * FROM {measure_id} WHERE ..."
df = self.connection.conn.execute(sql).fetchdf()

# NEW: Use measure framework
result = model.calculate_measure(measure_name, filters=filters)
df = result.data
```

**See:** `docs/STREAMLIT_REFACTORING_EXAMPLE.py` for exact implementation

---

### 2. `app/ui/components/exhibits/__init__.py` 🟡 HIGH

**What:** Update import to use model-based component

**Change:**
```python
# OLD:
from .weighted_aggregate_chart import render_weighted_aggregate_chart

# NEW:
from .weighted_aggregate_chart_model import render_weighted_aggregate_chart
```

---

### 3. `app/ui/components/exhibits/weighted_aggregate_chart.py` 🟢 LOW

**What:** Archive old component (optional)

**Action:**
```bash
mv app/ui/components/exhibits/weighted_aggregate_chart.py \
   docs/archive/experimental/weighted_aggregate_chart_legacy.py
```

---

## ✅ Benefits of Changes

| Aspect | Before | After |
|--------|--------|-------|
| **Setup** | Run build script to create views | No setup needed |
| **Backend** | DuckDB only | DuckDB + Spark |
| **Measure changes** | Re-run build script | Update YAML only |
| **Business logic** | In UI layer | In model layer |
| **SQL generation** | Manual | Automated via adapter |
| **Testing** | Hard to test views | Easy unit tests |
| **Performance** | Queries pre-built views | On-demand SQL (optimized) |

---

## 🧪 Testing Checklist

- [ ] Run pipeline tester: `python tests/pipeline_tester.py --verbose`
- [ ] Run basic examples: `python examples/measure_framework/01_basic_usage.py`
- [ ] Start Streamlit app: `streamlit run app/main.py`
- [ ] Navigate to page with weighted aggregate chart
- [ ] Verify chart loads without errors
- [ ] Test date range filtering
- [ ] Test ticker filtering
- [ ] Verify multiple measures display correctly
- [ ] Check legend toggle works
- [ ] Verify normalization (base 100)
- [ ] Check console for errors
- [ ] Test with empty/filtered data
- [ ] Test error handling (invalid measure)

---

## 📊 Current vs. Desired Architecture

### BEFORE (Materialized Views)
```
┌─────────────────────────────────────────────────┐
│ 1. Run build script (manual step)             │
│    python scripts/build_weighted_aggregates... │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 2. Creates materialized views in silver layer │
│    - equal_weighted_index                      │
│    - volume_weighted_index                     │
│    - market_cap_weighted_index                 │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 3. NotebookSession queries views directly      │
│    SELECT * FROM equal_weighted_index WHERE... │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 4. Chart renders pre-calculated data           │
└─────────────────────────────────────────────────┘

Issues:
❌ Manual build step
❌ DuckDB only (no Spark)
❌ Views can get stale
❌ Storage overhead
```

### AFTER (Unified Measure Framework)
```
┌─────────────────────────────────────────────────┐
│ 1. Exhibit config references measures          │
│    value_measures: ['volume_weighted_index']   │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 2. NotebookSession calls measure framework     │
│    model.calculate_measure('volume_weighted...')│
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 3. MeasureExecutor generates SQL via adapter   │
│    Backend-specific optimized SQL              │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 4. Chart renders real-time calculated data     │
└─────────────────────────────────────────────────┘

Benefits:
✅ No manual steps
✅ DuckDB + Spark support
✅ Always fresh data
✅ No storage overhead
✅ Easier to add measures
```

---

## 🔧 Migration Steps (2 hours)

### Step 1: Backup (5 min)
```bash
git checkout -b streamlit-measure-integration
cp app/notebook/api/notebook_session.py notebook_session.py.backup
```

### Step 2: Update notebook_session.py (1 hour)
- Replace `_get_weighted_aggregate_data()` method (lines 345-448)
- Copy implementation from `docs/STREAMLIT_REFACTORING_EXAMPLE.py`
- Key change: Use `model.calculate_measure()` instead of querying views

### Step 3: Update imports (5 min)
- Edit `app/ui/components/exhibits/__init__.py`
- Change import to use `weighted_aggregate_chart_model`

### Step 4: Test (30 min)
```bash
# Unit tests
pytest tests/integration/test_measure_pipeline.py -v

# Pipeline test
python tests/pipeline_tester.py --verbose

# Streamlit app
streamlit run app/main.py
```

### Step 5: Archive old component (5 min)
```bash
mkdir -p docs/archive/experimental
mv app/ui/components/exhibits/weighted_aggregate_chart.py \
   docs/archive/experimental/weighted_aggregate_chart_legacy.py
```

### Step 6: Commit (10 min)
```bash
git add .
git commit -m "refactor: Integrate Streamlit with unified measure framework"
git push -u origin streamlit-measure-integration
# Create PR
```

---

## 🚨 What Could Go Wrong

### Issue 1: Model not initialized
**Error:** `Model 'company' not available`

**Fix:** Ensure model is loaded in notebook session:
```python
session.model_sessions['company'] = {
    'model': model_instance,
    'initialized': True
}
```

---

### Issue 2: Measure not found
**Error:** `Measure 'volume_weighted_index' not defined`

**Fix:** Check that measure exists in `configs/models/company.yaml`:
```yaml
measures:
  volume_weighted_index:
    type: weighted
    weighting_method: volume
    ...
```

---

### Issue 3: Wrong column names
**Error:** `Missing required columns: weighted_value`

**Fix:** Ensure measure returns correct column names. Weighted measures should return `weighted_value`, simple measures return `measure_value`. The refactored code handles renaming.

---

### Issue 4: Performance slower than views
**Observation:** On-demand calculation might feel slower than querying pre-built views

**Fix:**
1. SQL is optimized by backend adapter
2. For frequently-used measures, can still materialize if needed
3. Add caching layer if needed
4. In practice, should be <1s for most queries

---

## 📚 Documentation References

| Document | Purpose |
|----------|---------|
| `STREAMLIT_REFACTORING_PLAN.md` | Detailed refactoring plan with rationale |
| `STREAMLIT_REFACTORING_EXAMPLE.py` | Exact code implementation with comments |
| `IMPLEMENTATION_SUMMARY.md` | Overview of measure framework architecture |
| `TESTING_GUIDE.md` | Testing strategy and examples |
| `BACKEND_ABSTRACTION_STRATEGY.md` | Backend abstraction design |

---

## 💬 Key Decisions

### Why not keep materialized views?
- Views duplicate measure definitions (maintenance burden)
- Views are DuckDB-only (no Spark support)
- Views can get stale (data freshness issues)
- On-demand calculation is fast enough (<1s typical)
- Easier to add/modify measures (just update YAML)

### Why hard cutover vs. gradual migration?
- Only 3 files affected (low risk)
- Measure framework already tested and working
- Cleaner code without feature flags
- Can complete in single session
- Easy to rollback if needed (git revert)

### Why archive old component instead of delete?
- Keep reference for understanding old approach
- May be useful for debugging/comparison
- Can permanently delete after migration is stable

---

## ✨ Success Criteria

After migration is complete, you should be able to:

1. ✅ Start Streamlit app without running any build scripts
2. ✅ View weighted aggregate charts with real-time data
3. ✅ Add new measures by updating YAML only
4. ✅ Use same measures in both DuckDB and Spark environments
5. ✅ Debug measures using `explain_measure()` method
6. ✅ Test measures with unit tests
7. ✅ Filter charts by date/ticker/etc.
8. ✅ See consistent behavior across all exhibit types

---

## 🎉 Next Steps After Migration

Once Streamlit integration is complete:

1. **Remove build script dependency**
   - Mark `build_weighted_aggregates_duckdb.py` as deprecated
   - Update setup documentation
   - Eventually delete materialized views (frees storage)

2. **Add new weighted measures**
   - Just update `configs/models/company.yaml`
   - No code changes needed
   - Instantly available in Streamlit

3. **Extend to other exhibit types**
   - Apply same pattern to forecast charts
   - Use measure framework for all calculations
   - Move business logic from UI to model layer

4. **Add caching if needed**
   - Implement result caching layer
   - Cache frequently-used measures
   - Configurable cache TTL

5. **Multi-backend support**
   - Test with Spark backend
   - Verify same results between DuckDB and Spark
   - Document any backend-specific behavior

---

## 📞 Need Help?

- **Questions about measure framework:** See `docs/TESTING_GUIDE.md`
- **Debugging:** Use `model.measures.explain_measure('measure_name')` to see SQL
- **Examples:** See `examples/measure_framework/01_basic_usage.py`
- **Common issues:** See `examples/measure_framework/02_troubleshooting.py`
- **Testing:** See `tests/pipeline_tester.py` for comprehensive validation

---

**Ready to start? Begin with Step 1 in Migration Steps above! 🚀**
