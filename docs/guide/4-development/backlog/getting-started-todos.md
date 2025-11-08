# Getting Started & Documentation TODOs

This document tracks improvements to onboarding, documentation, and tutorials to make de_Funk more accessible to new users.

**Last Updated:** 2025-11-08

---

## Table of Contents

- [Documentation Improvements](#documentation-improvements)
- [Onboarding Enhancements](#onboarding-enhancements)
- [Tutorial Additions](#tutorial-additions)
- [Examples and Templates](#examples-and-templates)
- [Reference Documentation](#reference-documentation)
- [Video and Interactive Content](#video-and-interactive-content)

---

## Documentation Improvements

### High Priority

#### DOC-GS-001: Improve Quickstart Guide
**Status:** Not Started
**Priority:** High
**Effort:** 2-3 days

**Description:**
Current quickstart is too long and complex for first-time users. Need a 5-minute "hello world" version.

**Requirements:**
- [ ] Single command setup (Docker Compose)
- [ ] Pre-loaded sample data (no API keys needed)
- [ ] Simple query example
- [ ] Expected output shown
- [ ] Clear "next steps" section

**Success Criteria:**
- New user can see results in <5 minutes
- No external dependencies required
- Works on Windows, Mac, Linux

---

#### DOC-GS-002: Add Troubleshooting Guide
**Status:** Not Started
**Priority:** High
**Effort:** 3-5 days

**Description:**
Comprehensive troubleshooting guide for common errors and issues.

**Sections Needed:**
- [ ] Installation issues (Java, Spark, DuckDB)
- [ ] API connection errors (rate limits, auth)
- [ ] Data pipeline failures (schema mismatches, null data)
- [ ] Model build errors (missing edges, invalid paths)
- [ ] Performance issues (slow queries, memory errors)
- [ ] Configuration problems (YAML syntax, missing files)

**Format:**
```
## Error: "Cannot resolve column 'ticker'"

**Cause:** Column name mismatch in YAML config

**Solution:**
1. Check Bronze table schema: `df.printSchema()`
2. Verify column name in config matches exactly
3. Common aliases: ticker/symbol, date/trade_date

**Example:**
...
```

---

#### DOC-GS-003: Create Architecture Decision Records (ADRs)
**Status:** Not Started
**Priority:** Medium
**Effort:** 2-3 days

**Description:**
Document key architectural decisions and rationale.

**ADRs to Create:**
- [ ] ADR-001: Why YAML-driven architecture?
- [ ] ADR-002: Why dual backend (Spark + DuckDB)?
- [ ] ADR-003: Why Parquet over Delta Lake?
- [ ] ADR-004: Why graph-based model architecture?
- [ ] ADR-005: Why markdown notebooks over Jupyter?
- [ ] ADR-006: Why Bronze/Silver (not Bronze/Silver/Gold)?

**Template:**
```markdown
# ADR-001: Title

## Status
Accepted

## Context
Problem or decision to be made...

## Decision
What we decided to do...

## Consequences
- Positive: ...
- Negative: ...
- Neutral: ...

## Alternatives Considered
1. Option A: ...
2. Option B: ...
```

---

#### DOC-GS-004: Improve Error Messages
**Status:** Not Started
**Priority:** High
**Effort:** 5-7 days (code + docs)

**Description:**
Add helpful error messages with suggestions for fixes.

**Current Problems:**
- Generic error messages ("Error building model")
- No suggestions for resolution
- Stack traces are overwhelming
- Hard to find root cause

**Improvements:**
- [ ] Wrap common errors with helpful messages
- [ ] Suggest likely fixes
- [ ] Link to relevant docs
- [ ] Show configuration snippet that caused error
- [ ] Add `--debug` flag for verbose output

**Example:**
```
❌ Error: Cannot find table 'dim_company' in model 'company'

Possible causes:
1. Table not defined in configs/models/company.yaml schema section
2. Model not built yet (run model.build() first)
3. Typo in table name (check schema.dimensions and schema.facts)

Hint: Available tables: dim_exchange, fact_prices, fact_news

See: docs/guide/2-models/tables.md
```

---

### Medium Priority

#### DOC-GS-005: Add FAQ Section
**Status:** Not Started
**Priority:** Medium
**Effort:** 2-3 days

**Description:**
Frequently asked questions with clear answers.

**Questions to Cover:**
- [ ] When should I use Spark vs DuckDB?
- [ ] How do I add a new data source?
- [ ] How do I create a custom transformation?
- [ ] How do I optimize query performance?
- [ ] How do I deploy to production?
- [ ] What's the difference between dimensions and facts?
- [ ] How do I join data from multiple models?
- [ ] How do I handle missing data?
- [ ] What are the system requirements?
- [ ] How do I backup my data?

---

#### DOC-GS-006: Create Glossary
**Status:** Not Started
**Priority:** Medium
**Effort:** 1-2 days

**Description:**
Comprehensive glossary of terms used in de_Funk.

**Terms to Define:**
- [ ] Bronze, Silver layers
- [ ] Facet, Provider, Ingestor
- [ ] Node, Edge, Path
- [ ] Dimension, Fact, Measure
- [ ] Model, Session, Registry
- [ ] Transform, Postprocess
- [ ] Exhibit, Filter, Notebook
- [ ] Storage Router, DAL
- [ ] Watermark, Incremental

**Format:**
```markdown
## Bronze Layer
Raw, unprocessed data exactly as received from source APIs.
Stored in Parquet format with minimal transformations.

**Related:** Silver Layer, Data Pipeline
**Example:** `storage/bronze/polygon/daily_prices/`
```

---

## Onboarding Enhancements

### High Priority

#### DOC-GS-007: Interactive Tutorial
**Status:** Not Started
**Priority:** High
**Effort:** 1-2 weeks

**Description:**
Step-by-step interactive tutorial that runs in the browser.

**Modules:**
1. [ ] Introduction to de_Funk concepts
2. [ ] Exploring existing models
3. [ ] Running your first query
4. [ ] Creating a simple dashboard
5. [ ] Adding a custom filter
6. [ ] Understanding the data pipeline
7. [ ] Creating a custom model

**Technology:**
- Jupyter Lite or similar browser-based environment
- Pre-loaded sample data
- Interactive code cells
- Automated validation of results

---

#### DOC-GS-008: Onboarding Checklist
**Status:** Not Started
**Priority:** Medium
**Effort:** 1 day

**Description:**
Clear checklist for new users to follow.

**Checklist Items:**
- [ ] ✅ Install dependencies (Java, Python, DuckDB)
- [ ] ✅ Clone repository
- [ ] ✅ Run setup script
- [ ] ✅ Verify installation (`python -m pytest tests/`)
- [ ] ✅ Run sample pipeline (`python run_full_pipeline.py --top-n 100`)
- [ ] ✅ View sample data in UI (`streamlit run app.py`)
- [ ] ✅ Explore a notebook
- [ ] ✅ Run a custom query
- [ ] ✅ Create a simple dashboard
- [ ] ✅ Read the architecture guide

**Progress Tracking:**
Automatically track progress and show completion percentage.

---

### Medium Priority

#### DOC-GS-009: User Personas and Paths
**Status:** Not Started
**Priority:** Medium
**Effort:** 2-3 days

**Description:**
Define user personas and recommended learning paths.

**Personas:**
1. **Data Analyst** - Uses existing models and dashboards
2. **Data Engineer** - Builds pipelines and integrations
3. **Developer** - Extends platform with custom code
4. **Researcher** - Performs ad-hoc analysis
5. **Executive** - Views high-level dashboards

**For Each Persona:**
- Background and goals
- Recommended starting point
- Key skills needed
- Typical workflows
- Example use cases
- Recommended reading order

---

#### DOC-GS-010: Migration Guides
**Status:** Not Started
**Priority:** Low
**Effort:** 3-5 days

**Description:**
Guides for migrating from other platforms.

**Migration From:**
- [ ] Jupyter notebooks → de_Funk notebooks
- [ ] Tableau/PowerBI → de_Funk dashboards
- [ ] Custom ETL scripts → de_Funk pipelines
- [ ] SQL queries → de_Funk models
- [ ] Pandas scripts → PySpark/DuckDB

---

## Tutorial Additions

### High Priority

#### DOC-GS-011: End-to-End Tutorial
**Status:** Not Started
**Priority:** High
**Effort:** 1 week

**Description:**
Complete tutorial building a real analysis from scratch.

**Tutorial: "Building a Stock Analysis Dashboard"**

**Steps:**
1. [ ] Define the business question
2. [ ] Identify data sources needed
3. [ ] Set up API credentials
4. [ ] Configure data ingestion
5. [ ] Build the domain model (YAML)
6. [ ] Create transformations
7. [ ] Define measures
8. [ ] Build the dashboard (notebook)
9. [ ] Add filters and interactivity
10. [ ] Optimize performance
11. [ ] Deploy to production

**Deliverables:**
- Step-by-step written guide
- Complete code in `/examples/tutorials/stock-dashboard/`
- Video walkthrough (optional)

---

#### DOC-GS-012: Data Pipeline Tutorial
**Status:** Not Started
**Priority:** High
**Effort:** 3-5 days

**Description:**
Deep dive into building data pipelines.

**Topics:**
- [ ] Provider architecture
- [ ] Creating a custom facet
- [ ] Handling pagination
- [ ] Data normalization
- [ ] Error handling and retries
- [ ] Testing facets
- [ ] Performance optimization

**Example:**
Build a custom provider for a new API (e.g., Alpha Vantage)

---

#### DOC-GS-013: Model Building Tutorial
**Status:** Not Started
**Priority:** High
**Effort:** 3-5 days

**Description:**
Comprehensive guide to building models.

**Topics:**
- [ ] Understanding the graph architecture
- [ ] Defining nodes (dimensions and facts)
- [ ] Creating edges (relationships)
- [ ] Materializing paths (joins)
- [ ] Adding measures
- [ ] Custom transformations
- [ ] Testing models
- [ ] Performance tuning

**Example:**
Build a "Portfolio Model" from scratch

---

### Medium Priority

#### DOC-GS-014: Advanced Querying Tutorial
**Status:** Not Started
**Priority:** Medium
**Effort:** 2-3 days

**Description:**
Advanced query patterns and techniques.

**Topics:**
- [ ] Complex filters and joins
- [ ] Window functions
- [ ] Aggregations and rollups
- [ ] Subqueries and CTEs
- [ ] Cross-model queries
- [ ] Performance optimization
- [ ] Query debugging

---

#### DOC-GS-015: Dashboard Design Tutorial
**Status:** Not Started
**Priority:** Medium
**Effort:** 2-3 days

**Description:**
Best practices for building effective dashboards.

**Topics:**
- [ ] Dashboard layout principles
- [ ] Choosing the right chart type
- [ ] Filter design
- [ ] Interactivity patterns
- [ ] Mobile responsiveness
- [ ] Performance considerations
- [ ] Accessibility

---

## Examples and Templates

### High Priority

#### DOC-GS-016: Example Repository
**Status:** In Progress
**Priority:** High
**Effort:** 1 week

**Description:**
Comprehensive examples for all extension points.

**Examples Needed:**
- [x] Custom facet (`examples/facets/custom_facet_example.py`)
- [x] Custom provider (`examples/providers/custom_provider_example.py`)
- [x] Custom model (`examples/models/custom_model_example.py`)
- [x] Custom notebook (`examples/notebooks/custom_notebook_example.md`)
- [x] Ad-hoc queries (`examples/adhoc-analysis/session_query_examples.py`)
- [ ] Custom transformation
- [ ] Custom measure
- [ ] Custom exhibit type
- [ ] Integration with Pandas
- [ ] Integration with Plotly

---

#### DOC-GS-017: Project Templates
**Status:** Not Started
**Priority:** Medium
**Effort:** 3-5 days

**Description:**
Cookiecutter templates for common use cases.

**Templates:**
- [ ] **new-provider** - Scaffold a new API provider
- [ ] **new-model** - Scaffold a new domain model
- [ ] **new-dashboard** - Scaffold a new dashboard
- [ ] **new-analysis** - Scaffold an ad-hoc analysis script

**Usage:**
```bash
cookiecutter templates/new-provider
# Prompts for provider name, base URL, auth type, etc.
# Generates provider/, facets/, registry.py, tests/
```

---

## Reference Documentation

### High Priority

#### DOC-GS-018: API Reference
**Status:** Not Started
**Priority:** High
**Effort:** 1 week (setup auto-generation)

**Description:**
Auto-generated API documentation from docstrings.

**Tools:**
- Sphinx or MkDocs
- Napoleon for Google-style docstrings
- Auto-API plugin

**Coverage:**
- [ ] All public classes and methods
- [ ] Module-level documentation
- [ ] Type hints
- [ ] Examples in docstrings
- [ ] Cross-references

---

#### DOC-GS-019: YAML Schema Reference
**Status:** Not Started
**Priority:** High
**Effort:** 3-5 days

**Description:**
Complete reference for all YAML configurations.

**Schemas to Document:**
- [ ] Model config (`configs/models/*.yaml`)
- [ ] Provider config (`configs/providers/*.yaml`)
- [ ] Storage config (`configs/storage.yaml`)
- [ ] Notebook config (frontmatter)
- [ ] Filter definitions
- [ ] Exhibit definitions

**Format:**
```markdown
## Model Configuration

### `graph.nodes`

**Type:** List of objects
**Required:** Yes

**Schema:**
- `id` (string, required) - Unique node identifier
- `from` (string, required) - Source table (bronze.table_name)
- `transforms` (list, optional) - Transformations to apply
- `description` (string, optional) - Documentation

**Example:**
```yaml
nodes:
  - id: dim_company
    from: bronze.ref_ticker
    transforms:
      - select: ["ticker", "name"]
```
```

---

### Medium Priority

#### DOC-GS-020: Configuration Examples
**Status:** Not Started
**Priority:** Medium
**Effort:** 2-3 days

**Description:**
Library of configuration examples for common scenarios.

**Examples:**
- [ ] Simple dimension table
- [ ] Fact table with partitions
- [ ] Many-to-many relationship
- [ ] Slowly-changing dimension
- [ ] Time-based aggregation
- [ ] Complex transformation pipeline
- [ ] Cross-model join
- [ ] Custom measure calculation

---

## Video and Interactive Content

### Medium Priority

#### DOC-GS-021: Video Tutorials
**Status:** Not Started
**Priority:** Medium
**Effort:** 2-3 weeks

**Description:**
Screen recordings for key workflows.

**Videos Needed:**
1. [ ] Platform Overview (5 min)
2. [ ] Quick Start (10 min)
3. [ ] Building Your First Model (15 min)
4. [ ] Creating a Dashboard (10 min)
5. [ ] Adding a Data Source (15 min)
6. [ ] Performance Optimization (10 min)
7. [ ] Troubleshooting Common Errors (10 min)

**Platform:** YouTube (unlisted or public)

---

#### DOC-GS-022: Interactive Playground
**Status:** Not Started
**Priority:** Low
**Effort:** 2-3 weeks

**Description:**
Web-based playground for trying de_Funk without installation.

**Features:**
- Pre-loaded sample data
- In-browser code editor
- Live query results
- Example queries to try
- Share results via URL

**Technology:** Pyodide (Python in browser) + DuckDB WASM

---

## Documentation Infrastructure

### Medium Priority

#### DOC-GS-023: Documentation Site
**Status:** Not Started
**Priority:** Medium
**Effort:** 1 week

**Description:**
Dedicated documentation website (replacing README files).

**Features:**
- [ ] Searchable documentation
- [ ] Version switcher
- [ ] Dark mode
- [ ] Mobile responsive
- [ ] Code syntax highlighting
- [ ] Copy code buttons
- [ ] Breadcrumb navigation

**Technology:** MkDocs Material or Docusaurus

---

#### DOC-GS-024: Documentation Tests
**Status:** Not Started
**Priority:** Medium
**Effort:** 3-5 days

**Description:**
Automated testing of documentation code examples.

**Features:**
- [ ] Extract code from docs
- [ ] Run as tests
- [ ] Verify expected output
- [ ] Catch broken examples
- [ ] Run in CI/CD

**Tool:** `pytest-codeblocks` or custom solution

---

## Success Metrics

**Documentation Quality:**
- [ ] All code examples are tested
- [ ] All public APIs are documented
- [ ] Search functionality works well
- [ ] Mobile experience is good
- [ ] Load time <2 seconds

**User Success:**
- [ ] New user can complete quickstart in <10 minutes
- [ ] 80% of support questions answered by docs
- [ ] Positive feedback on documentation clarity
- [ ] Low bounce rate on docs site

**Maintenance:**
- [ ] Automated doc generation
- [ ] Automated testing of examples
- [ ] Clear process for updating docs
- [ ] Community contributions to docs

---

## Priority Summary

- **Critical:** 4 items
- **High:** 12 items
- **Medium:** 12 items
- **Low:** 2 items
- **Total:** 30 items

## Related Documents

- [TODO Tracker](../todo-tracker.md) - All development tasks
- [Roadmap](../roadmap.md) - Product roadmap
- [Contributing Guide](../../1-getting-started/contributing.md) - How to contribute
