# TODO — Known Issues & Feature Backlog

**Last Updated**: 2026-03-19

---

## Critical — API Consolidation

See [Proposal 016](proposals/016-api-consolidation.md) for full analysis.

Three overlapping query layers exist (`models/api/`, `notebook/`, `api/`). The consolidation proposal outlines a 4-phase migration to a single `core/query/` layer. Key outcomes:
- Server-side aggregation (GROUP BY) — currently missing from FastAPI
- Dynamic join planning — currently static resolver graph
- Universal date filter translation — currently missing
- Safe deletion of ~2,000 lines of dead/duplicate code

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
- Root cause fix: event loop architecture (see below)

### Ticker picker DOM performance
- 9,652 tickers rendered as DOM rows — capped to 200 with search filter
- For true scalability: implement virtual scrolling (render only visible rows)

---

## Feature Backlog

### Event loop architecture (plugin refactor) — HIGH PRIORITY
- Replace the current reactive fire-everything model with a proper event loop
- The Obsidian plugin's `filter-bus.ts` + `config-panel.ts` need restructuring into:
  1. **State store** — single source of truth for filters, control selections, active page, query results
  2. **Event bus** — typed events (FilterChanged, ControlToggled, DataReady, RenderDirty)
  3. **Reconciler** — diffs old vs new state, emits minimal RenderDirty events (only changed exhibits)
  4. **Query scheduler** — batches, deduplicates, and prioritizes API calls per render tick
- This solves the query storm (30 queries per filter change), duplicate renders, and progressive slowdown
- The loop pattern: collect events → dispatch to handlers → reconcile state → render dirty exhibits
- Same architecture supports any future renderer (web UI, etc.) — the renderer just subscribes to RenderDirty and reads from the state store
- This replaces the earlier TUI proposal — no terminal UI is needed; the event loop is the investment

### Top-N / binning for charts
- User requested: "top 5 by industry" for bar/pie charts
- Add `top_n` grouped parameter to graphical handler — aggregate, sort, take top N, bucket rest as "Other"
- Useful for sector/company breakdowns with many categories

### Bronze basic functions
- Incorporate simple big table function to support access and adjustments
- Example: enabling functions like `month()` on date fields so simple bin and aggregations work
- Bridge between raw Bronze data and analytics without requiring Silver builds

### Embedded cosine similarity in data pipeline
- Add an embedding + cosine similarity step to the Silver build pipeline
- Use case: find similar entities across dimensions (similar companies by financials, similar crimes by attributes, similar properties by characteristics)
- Pipeline step: after Silver tables are built, compute embeddings on key dimension columns and store similarity scores
- Could use sentence-transformers or a lightweight embedding model for text fields, numeric normalization for quantitative fields
- Store as a similarity matrix table (entity_a, entity_b, similarity_score) per domain
- Enables "find similar" queries from the Obsidian plugin and recommendation-style analytics
- Enable analytical reduction of dimensions — example: Chicago budget having changing field names over years, similarity matching could normalize them

### Grouped candlestick charts
- Plotly doesn't support grouped candlesticks natively
- Sector-level OHLC: `group_by` added to box handler, renders as grouped box plots instead
- For true candlestick grouping: would need subplot layout (one candlestick per group)

### Bronze cross-endpoint joins
- Currently Bronze queries hit a single API endpoint
- No way to join across endpoints (e.g., crimes × community areas)
- Would require a Bronze-level join planner similar to Silver's FieldResolver

### Bronze computed measures
- No support for computed measures (e.g., arrest rate = arrests / total) on Bronze queries
- Would need expression evaluation in the Bronze query handler

---

## Model Guide Audit (2026-03-19)

Audit of `domains/_model_guides_/` — each guide now has inline `> Status: PLANNED` notes on unimplemented features.

### Parse-only features (config reads, build/query never uses)

| Guide | Feature | What's missing |
|-------|---------|---------------|
| **views.md** | Views (derived, rollup, assumptions, grain) | Build pipeline has no view materialization code |
| **federation.md** | Federation (children, union_key, union_of) | Build pipeline has no Silver-to-Silver union code. Note: `__union__` is Bronze source union, not federation |
| **graph.md** | `auto_edges` | Edges must be declared explicitly; auto-injection not implemented |
| **graph.md** | `graph.paths` (multi-hop traversals) | Dead code in old `models/api/`; FastAPI query layer doesn't use paths |
| **behaviors.md** | Behavior validation | Parsed as metadata, never enforced against actual config blocks |
| **subsets.md** | Pattern 2 (separate models) | No special handling — each model builds independently |
| **subsets.md** | Pattern 3 (filter-only) | Discriminator filters not auto-generated |
| **tables.md** | `unique_key` enforcement | Parsed but no dedup or uniqueness validation during build |

### Fully implemented guides
depends_on, domain_model, extends, materialization, measures, source_onboarding, sources, storage, tables (except unique_key), subsets Pattern 1 (wide table auto-absorption), domain_base (except auto_edges/behaviors)

---

## Cleanup

### Streamlit references in pyproject.toml
- `streamlit` still listed as a dependency — remove from `[project.optional-dependencies]`
- Check for any remaining `streamlit` imports in `src/` or `scripts/`

### Dead code audit
- `src/de_funk/models/api/` — see Proposal 016 for which modules are load-bearing vs dead
- `src/de_funk/notebook/` — check if remaining modules (parsers, filters, expressions, yaml_utils) are used by anything after Streamlit removal
- `src/de_funk/services/` — verify fully cleaned

### Exhibits directory cleanup
- `exhibits/charts/` — single `line_chart.md`, check if referenced anywhere
- `exhibits/metrics/` — empty directory
- `exhibits/tables/` — empty directory
- `exhibits/themes/financial.yaml` — check if theme system is implemented; if not, remove
- Keep: `exhibits/_base/`, `exhibits/types/`, `exhibits/testing/`
