# YAML Frontmatter Reference

Syntax reference for every YAML frontmatter section used in de_Funk domain model configs.

| Guide | What It Covers |
|---|---|
| [domain_model.md](domain_model.md) | Complete model.md reference (type, version, depends_on, graph, build, hooks, measures) |
| [domain_base.md](domain_base.md) | Base template files in domains/_base/ |
| [tables.md](tables.md) | Table definition files (schema, primary_key, table_type, derived columns) |
| [sources.md](sources.md) | Source mapping files (API field → schema column) |
| [source_onboarding.md](source_onboarding.md) | Step-by-step guide for adding a new data source |
| [graph.md](graph.md) | Graph edge definitions (join paths between tables) |
| [extends.md](extends.md) | Inheritance — how models extend base templates |
| [measures.md](measures.md) | Measure definitions (simple, computed, window) |
| [subsets.md](subsets.md) | Declarative data slicing by dimension discriminator |
| [views.md](views.md) | Layered calculations and rollup aggregations |
| [federation.md](federation.md) | Cross-model union queries via _base/ |
| [storage.md](storage.md) | Storage and source discovery configuration |
| [materialization.md](materialization.md) | What gets built, in what order, and how |
| [behaviors.md](behaviors.md) | Cross-cutting capabilities on base templates |
| [depends_on.md](depends_on.md) | Model build ordering |

These guides are the single source of truth for YAML syntax. The domain model configs in `domains/models/` follow these formats exactly.
