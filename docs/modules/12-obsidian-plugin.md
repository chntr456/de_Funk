---
title: "Obsidian Plugin"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - obsidian-plugin/src/api-client.ts
  - obsidian-plugin/src/contract.ts
  - obsidian-plugin/src/filter-bus.ts
  - obsidian-plugin/src/filter-sidebar.ts
  - obsidian-plugin/src/frontmatter.ts
  - obsidian-plugin/src/main.ts
  - obsidian-plugin/src/processors/config-panel-renderer.ts
  - obsidian-plugin/src/processors/config-panel.ts
  - obsidian-plugin/src/processors/de-funk.ts
  - obsidian-plugin/src/render/format.ts
  - obsidian-plugin/src/render/graphical.ts
  - obsidian-plugin/src/render/metric-cards.ts
  - obsidian-plugin/src/render/pivot.ts
  - obsidian-plugin/src/render/scroll.ts
  - obsidian-plugin/src/render/tabular.ts
  - obsidian-plugin/src/resolver.ts
  - obsidian-plugin/src/settings.ts
---

# Obsidian Plugin

> TypeScript plugin that renders exhibit blocks in Obsidian notes by calling the FastAPI backend.

## Purpose & Design Decisions

### What Problem This Solves

<!-- TODO -->

### Connection to Python Backend

The plugin calls these API endpoints:

| Endpoint | Plugin File | What It Does |
|----------|------------|-------------|
| `POST /api/query` | `api-client.ts` | Execute exhibit queries (charts, tables, metrics) |
| `GET /api/dimensions/{ref}` | `api-client.ts` | Populate filter sidebar dropdowns |
| `GET /api/domains` | `api-client.ts` | Discover available domains |
| `POST /api/bronze/query` | `api-client.ts` | Query Bronze layer directly |
| `GET /api/health` | `api-client.ts` | Health check on startup |

## File Reference

| File | Purpose |
|------|---------|
| `api-client.ts` | <!-- TODO --> |
| `contract.ts` | <!-- TODO --> |
| `filter-bus.ts` | <!-- TODO --> |
| `filter-sidebar.ts` | <!-- TODO --> |
| `frontmatter.ts` | <!-- TODO --> |
| `main.ts` | <!-- TODO --> |
| `processors/config-panel-renderer.ts` | <!-- TODO --> |
| `processors/config-panel.ts` | <!-- TODO --> |
| `processors/de-funk.ts` | <!-- TODO --> |
| `render/format.ts` | <!-- TODO --> |
| `render/graphical.ts` | <!-- TODO --> |
| `render/metric-cards.ts` | <!-- TODO --> |
| `render/pivot.ts` | <!-- TODO --> |
| `render/scroll.ts` | <!-- TODO --> |
| `render/tabular.ts` | <!-- TODO --> |
| `resolver.ts` | <!-- TODO --> |
| `settings.ts` | <!-- TODO --> |

## How to Use

### Block Syntax

See [docs/obsidian-plugin.md](../obsidian-plugin.md) for full block syntax reference.

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| <!-- TODO --> | | |
