# de_Funk Tagging & Category System

---

This document defines the tagging and categorization system for de_Funk documentation, optimized for Obsidian knowledge management.

---

## Tag Hierarchy

---

### **1. Domain Tags** - What area of knowledge

```
#finance           - Financial markets and instruments
#finance/equities  - Stock market specific
#finance/forecast  - Time series predictions
#economics         - Macroeconomic indicators
#economics/bls     - Bureau of Labor Statistics data
#municipal         - City and local government data
#reference         - Reference data (calendars, lookups)
```

---

### **2. Component Tags** - What part of the system

```
#component/pipeline     - Data ingestion pipeline
#component/model        - Data models
#component/notebook     - Interactive notebooks
#component/ui           - User interface
#component/storage      - Storage layer
#component/session      - Session management
```

---

### **3. Concept Tags** - Technical concepts

```
#concept/dimensional-modeling  - Star/snowflake schemas
#concept/etl                   - Extract, Transform, Load
#concept/analytics             - Data analysis
#concept/filtering             - Data filtering
#concept/aggregation           - Data aggregation
#concept/visualization         - Charts and graphs
#concept/api-integration       - External API integration
#concept/graph-modeling        - Graph-based data modeling
```

---

### **4. Data Source Tags** - Where data comes from

```
#source/polygon     - Polygon.io API
#source/bls         - Bureau of Labor Statistics
#source/chicago     - Chicago Data Portal
#source/generated   - System-generated data
```

---

### **5. Status Tags** - Maturity/stability

```
#status/stable       - Production-ready
#status/experimental - In development
#status/deprecated   - Being phased out
#status/planned      - Future feature
```

---

### **6. Type Tags** - Document type

```
#type/guide          - How-to guide
#type/reference      - Reference documentation
#type/example        - Code example
#type/architecture   - Architecture doc
#type/model          - Model documentation
#type/template       - Template for new docs
```

---

## Obsidian Features Used

---

### **YAML Frontmatter**

Every document should have frontmatter:

```yaml
---
title: "Document Title"
tags: [finance, component/model, concept/dimensional-modeling]
aliases: ["Alternative Name", "Shorthand"]
created: 2024-11-08
updated: 2024-11-08
status: stable
related:
  - "[[Related Document]]"
  - "[[Another Document]]"
---
```

---

### **Wiki Links**

Use double-bracket links for cross-references:

```markdown
See [[Company Model]] for details on stock data.
This builds on [[Core Model]] calendar dimension.
```

---

### **Backlinks**

Obsidian automatically tracks backlinks. Use them to:
- Link models to their dependencies
- Link how-tos to referenced components
- Link examples to their source docs

---

### **Graph View**

Tags and links create a knowledge graph:
- Models cluster by domain (#finance, #economics)
- Components show dependencies
- Concepts show relationships

---

## Tag Usage Guidelines

---

### **Model Documents**

```yaml
tags: [
  finance/equities,           # Domain
  component/model,            # Component type
  concept/dimensional-modeling, # Technical concept
  source/polygon,             # Data source
  status/stable               # Maturity
]
```

**Example:** Company Model
```yaml
tags: [finance/equities, component/model, concept/dimensional-modeling, source/polygon, status/stable]
```

---

### **Architecture Documents**

```yaml
tags: [
  component/pipeline,         # Component
  concept/etl,                # Concept
  type/architecture,          # Doc type
  status/stable               # Maturity
]
```

**Example:** Data Pipeline Overview
```yaml
tags: [component/pipeline, concept/etl, concept/api-integration, type/architecture, status/stable]
```

---

### **How-To Guides**

```yaml
tags: [
  type/guide,                 # Doc type
  component/model,            # What you're working with
  concept/dimensional-modeling, # Concept taught
  status/stable               # Maturity
]
```

**Example:** Create a Model Guide
```yaml
tags: [type/guide, component/model, concept/dimensional-modeling, status/stable]
```

---

### **Examples**

```yaml
tags: [
  type/example,               # Doc type
  component/pipeline,         # Component demonstrated
  concept/api-integration,    # Concept shown
  source/polygon              # If specific to a source
]
```

---

## External Concept Connections

---

### **Finance Concepts**

Connect to external knowledge:

```markdown
#finance/equities connects to:
- Stock exchanges
- Market indices
- Trading systems
- Portfolio management

#finance/forecast connects to:
- Time series analysis
- Predictive modeling
- Risk management
```

---

### **Economics Concepts**

```markdown
#economics connects to:
- Unemployment rate
- Inflation (CPI)
- GDP growth
- Labor statistics

#economics/bls connects to:
- Bureau of Labor Statistics
- Employment data
- Consumer prices
- Wage trends
```

---

### **Data Engineering Concepts**

```markdown
#concept/etl connects to:
- Data warehousing
- Medallion architecture
- Data quality
- Schema evolution

#concept/dimensional-modeling connects to:
- Star schema
- Snowflake schema
- Fact tables
- Dimension tables
- Kimball methodology
```

---

## Recommended Tag Combinations

---

### **For Model Documentation**

```
Domain + Component + Concept + Source + Status
Example: #finance/equities #component/model #concept/dimensional-modeling #source/polygon #status/stable
```

---

### **For How-To Guides**

```
Type + Component + Concept + Status
Example: #type/guide #component/pipeline #concept/api-integration #status/stable
```

---

### **For Architecture Docs**

```
Type + Component + Concept + Status
Example: #type/architecture #component/storage #concept/etl #status/stable
```

---

### **For Examples**

```
Type + Component + Concept
Example: #type/example #component/notebook #concept/visualization
```

---

## Obsidian Queries

---

### **Find All Model Documentation**

```dataview
LIST
FROM #component/model
SORT file.name ASC
```

---

### **Find Stable Finance Components**

```dataview
TABLE tags, updated
FROM #finance AND #status/stable
SORT updated DESC
```

---

### **Find All How-To Guides**

```dataview
LIST
FROM #type/guide
SORT file.name ASC
```

---

### **Find Documents by Data Source**

```dataview
TABLE tags, title
FROM #source/polygon OR #source/bls OR #source/chicago
GROUP BY source
```

---

## Applying Tags to Existing Docs

---

### **Getting Started Section**

| Document | Tags |
|----------|------|
| Quickstart | `#type/guide #status/stable` |
| Architecture Overview | `#type/architecture #concept/etl #concept/dimensional-modeling #status/stable` |
| Installation | `#type/guide #status/stable` |

---

### **Models Section**

| Document | Tags |
|----------|------|
| Core Model | `#reference #component/model #concept/dimensional-modeling #source/generated #status/stable` |
| Company Model | `#finance/equities #component/model #concept/dimensional-modeling #source/polygon #status/stable` |
| Forecast Model | `#finance/forecast #component/model #concept/analytics #status/stable` |
| Macro Model | `#economics/bls #component/model #concept/dimensional-modeling #source/bls #status/stable` |
| City Finance Model | `#municipal #economics #component/model #concept/dimensional-modeling #source/chicago #status/stable` |

---

### **Architecture Section**

| Document | Tags |
|----------|------|
| Data Pipeline Components | `#component/pipeline #concept/etl #concept/api-integration #type/architecture #status/stable` |
| Models System | `#component/model #concept/dimensional-modeling #concept/graph-modeling #type/architecture #status/stable` |
| Notebook System | `#component/notebook #concept/analytics #concept/visualization #type/architecture #status/stable` |
| UI Application | `#component/ui #concept/visualization #type/architecture #status/stable` |

---

## Benefits of This System

---

### **1. Discovery**
- Find related documents by tag
- Explore knowledge graph visually
- Query by multiple criteria

### **2. Organization**
- Clear hierarchical structure
- Consistent categorization
- Easy navigation

### **3. Connections**
- Link to external concepts
- Track dependencies
- See relationships

### **4. Maintenance**
- Track document status
- Find outdated docs
- Identify gaps

---

## Future Enhancements

---

- Add `#priority/high` tags for critical docs
- Add `#audience/analyst` for role-based views
- Add `#version/v1` for version tracking
- Add `#difficulty/beginner` for learning paths

---

**Last Updated:** 2024-11-08
**Status:** #status/stable
**Type:** #type/reference
