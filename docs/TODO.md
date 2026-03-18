# TODO — Known Issues & Feature Backlog

**Last Updated**: 2026-03-18

---

## Bugs

### Sort handling (Silver + Bronze)
- `sort.by` with bare keys (e.g., `y`, `incidents`) gets injected raw into SQL — crashes with `Referenced column "y" not found`
- `sort.by` with domain refs (e.g., `securities.stocks.volume`) also injected raw — needs resolver pass before SQL generation
- Affects: bar charts, pivot `sort.rows.by`, `table.data` `sort_by`
- Fix: resolve sort keys through `FieldResolver`/`BronzeResolver` before building ORDER BY clause

### Obsidian `addChild` error
- `Uncaught (in promise) TypeError: e.load is not a function` in `addChild`
- The filter unsubscribe cleanup object passed to `ctx.addChild()` doesn't implement Obsidian's `MarkdownRenderChild` interface
- Fix: extend `MarkdownRenderChild` instead of passing a plain `{ onunload }` object

### Table viewport scroll (pre-existing)
- Inline `!important` styles not creating bounded viewport on GT (Great Tables) exhibits
- Pivot tables with many rows overflow the container instead of scrolling
- Needs DOM debugging — likely a CSS containment issue

---

## Performance

### DuckDB progressive slowdown
- Server gets progressively unresponsive after repeated filter changes
- Suspected: DuckDB accumulating delta_scan state / memory without releasing
- Query timing middleware added to router dispatch for diagnostics — use logs to profile
- Next steps: check `duckdb_memory()` between queries, consider per-query connection pooling or periodic `PRAGMA memory_limit` reset

### Box handler unbounded rows
- Box/OHLCV handler returns all raw rows (30K+) with no aggregation and no LIMIT
- Should respect `max_sql_rows` from `configs/storage.json`

### Plugin query storm on filter change
- Single filter change fires ~30 queries in 3 seconds (all exhibits re-render, some duplicated)
- In-flight dedup added but cache is cleared before notify — first wave still hits server
- Consider: debounce filter bus (100ms), batch exhibit re-renders, or stagger queries

### Ticker picker DOM performance
- 9,652 tickers rendered as DOM rows — capped to 200 with search filter
- For true scalability: implement virtual scrolling (render only visible rows)

---

## Feature Backlog

### Top-N / binning for charts
- User requested: "top 5 by industry" for bar/pie charts
- Add `top_n` grouped parameter to graphical handler — aggregate, sort, take top N, bucket rest as "Other" 
- Useful for sector/company breakdowns with many categories and you can see the top N attribution

### Event loop architecture (plugin refactor)
- Replace the current reactive fire-everything model with a proper event loop
- The Obsidian plugin's `filter-bus.ts` + `config-panel.ts` need restructuring into:
  1. **State store** — single source of truth for filters, control selections, active page, query results
  2. **Event bus** — typed events (FilterChanged, ControlToggled, DataReady, RenderDirty)
  3. **Reconciler** — diffs old vs new state, emits minimal RenderDirty events (only changed exhibits)
  4. **Query scheduler** — batches, deduplicates, and prioritizes API calls per render tick
- This solves the query storm (30 queries per filter change), duplicate renders, and progressive slowdown
- The loop pattern: collect events → dispatch to handlers → reconcile state → render dirty exhibits
- Same architecture supports any future renderer (web UI, etc.) — the renderer just subscribes to RenderDirty and reads from the state store
- **Priority**: High — this is the root cause of most performance issues

### Bronze basic functions
- Incorporate simple big table function to support access and adjustments
- Example would be enabling functions like month() on date fields so simple bin and aggregations can be empowered

### Grouped candlestick charts
- Plotly doesn't support grouped candlesticks natively
- Sector-level OHLC: `group_by` added to box handler, renders as grouped box plots instead
- For true candlestick grouping: would need subplot layout (one candlestick per group)

---

## Cleanup

### Streamlit references in pyproject.toml
- `streamlit` still listed as a dependency — remove from `[project.optional-dependencies]`
- Check for any remaining `streamlit` imports in `src/` or `scripts/`

### Dead code audit
- `src/de_funk/notebook/` — check if remaining modules (parsers, filters, expressions, yaml_utils) are used by anything after Streamlit removal
- `src/de_funk/services/notebook_service.py` — already deleted, verify no dangling imports
