# Debug Scripts

**Purpose:** Debugging and diagnostic utilities for troubleshooting de_Funk issues

This folder contains scripts for diagnosing and debugging various issues in the de_Funk system.

---

## 🐛 Available Debug Scripts (8 scripts)

| Script | Purpose | Usage |
|--------|---------|-------|
| `check_parquet_path.py` | Validate Parquet file paths and check file existence | `python -m scripts.debug.check_parquet_path` |
| `debug_exchange_data.py` | Debug issues with exchange data (MIC codes, etc.) | `python -m scripts.debug.debug_exchange_data` |
| `debug_forecast_view.py` | Debug forecast view data and SQL queries | `python -m scripts.debug.debug_forecast_view` |
| `debug_session_injection.py` | Debug UniversalSession injection issues | `python -m scripts.debug.debug_session_injection` |
| `debug_weighted_views.py` | Debug weighted aggregate view generation | `python -m scripts.debug.debug_weighted_views` |
| `diagnose_view_data.py` | General view data diagnostic tool | `python -m scripts.debug.diagnose_view_data` |
| `drop_view.py` | Drop database views (utility) | `python -m scripts.debug.drop_view` |

---

## 📝 Common Use Cases

### Exchange Data Issues
```bash
# Debug exchange data and MIC codes
python -m scripts.debug.debug_exchange_data
```

### Forecast View Problems
```bash
# Debug forecast view generation
python -m scripts.debug.debug_forecast_view

# Diagnose view data issues
python -m scripts.debug.diagnose_view_data
```

### Weighted Aggregates
```bash
# Debug weighted view calculations
python -m scripts.debug.debug_weighted_views
```

### Session/Injection Issues
```bash
# Debug session injection
python -m scripts.debug.debug_session_injection
```

### File Path Validation
```bash
# Check Parquet file paths
python -m scripts.debug.check_parquet_path
```

---

## 🔍 When to Use Debug Scripts

- **Exchange issues:** Use `debug_exchange_data.py` when exchange_name is NULL or MIC codes are missing
- **Forecast problems:** Use `debug_forecast_view.py` when forecasts aren't showing in views
- **View errors:** Use `diagnose_view_data.py` for general view data issues
- **Weighted calculations:** Use `debug_weighted_views.py` when weighted aggregates are incorrect
- **Session problems:** Use `debug_session_injection.py` for cross-model query issues
- **File not found:** Use `check_parquet_path.py` to validate storage paths

---

## 💡 Tips

1. **Run after changes:** Debug scripts are useful after schema changes or model updates
2. **Check logs:** Most debug scripts output diagnostic information to console
3. **SQL inspection:** Many scripts show the SQL queries being generated
4. **Data sampling:** Debug scripts often show sample data to help identify issues

---

## 🆘 Troubleshooting

If a debug script fails:
1. Check that the model is built (`python -m scripts.build.build_all_models`)
2. Verify database connection (DuckDB file exists at `storage/duckdb/analytics.db`)
3. Ensure Bronze/Silver data exists
4. Check script docstring for specific requirements

---

**For more information, see the main scripts README: `/scripts/README.md`**
