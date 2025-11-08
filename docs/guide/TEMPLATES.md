# Documentation Templates

---

This document provides templates for creating new documentation files in the de_Funk guide.

---

## Table of Contents

---

- [Model Documentation Template](#model-documentation-template)
- [How-To Guide Template](#how-to-guide-template)
- [Architecture Component Template](#architecture-component-template)
- [Usage Tips](#usage-tips)

---

## Model Documentation Template

---

Use this template when documenting a new data model.

**File Location:** `docs/guide/2-models/implemented/your-model-name.md`

```markdown
---
title: "Your Model Name"
tags: [domain/category, component/model, concept/dimensional-modeling, source/api-name, status/stable]
aliases: ["Alternative Name", "Short Name"]
created: YYYY-MM-DD
updated: YYYY-MM-DD
status: stable
dependencies:
  - "[[Dependency Model]]"
used_by:
  - "[[Consumer Model]]"
---

# Your Model Name

---

> **Brief one-line description of the model**

Detailed description explaining what the model does, its purpose, and key features. Mention dependencies and consumers.

**Configuration:** `/path/to/configs/models/your-model.yaml`
**Implementation:** `/path/to/models/implemented/your-model/model.py`

---

## Table of Contents

---

- [Overview](#overview)
- [Schema Overview](#schema-overview)
- [Data Sources](#data-sources)
- [Detailed Schema](#detailed-schema)
- [Graph Structure](#graph-structure)
- [Measures](#measures)
- [How-To Guides](#how-to-guides)
- [Usage Examples](#usage-examples)
- [Design Decisions](#design-decisions)
- [Partitioning Strategy](#partitioning-strategy)

---

## Overview

---

### Purpose

The Model provides:
- Feature 1
- Feature 2
- Feature 3

### Key Features

- **Feature A** - Description
- **Feature B** - Description
- **Feature C** - Description

### Model Characteristics

| Attribute | Value |
|-----------|-------|
| **Model Name** | `model_name` |
| **Tags** | `tag1`, `tag2`, `tag3` |
| **Dependencies** | [[Dependency Model]] (description) |
| **Data Source** | API Name |
| **Storage Root** | `storage/silver/model_name` |
| **Format** | Parquet |
| **Tables** | X (Y dimensions, Z facts, N views) |
| **Dimensions** | Y |
| **Facts** | Z |
| **Measures** | N |
| **Update Frequency** | Daily/Weekly/Monthly |

---

## Schema Overview

---

### High-Level Summary

Brief description of the schema design (star/snowflake), data sources, and partitioning strategy.

**Quick Reference:**

| Table Type | Count | Purpose |
|------------|-------|---------|
| **Dimensions** | Y | Descriptive attributes (who, what, where) |
| **Facts** | Z | Measurable events (what happened) |
| **Materialized Views** | N | Pre-joined analytics tables |
| **Measures** | M | Pre-defined calculations |

### Dimensions (Who/What)

| Dimension | Rows | Primary Key | Purpose |
|-----------|------|-------------|---------|
| **dim_name** | ~X | key_column | Brief description |

### Facts (Events/Transactions)

| Fact | Grain | Partitions | Purpose |
|------|-------|------------|---------|
| **fact_name** | One row per... | partition_column | Brief description |

### Star Schema Diagram

```
                    ┌─────────────────┐
                    │  [[Core Model]] │
                    │  dim_calendar   │
                    └────────┬────────┘
                             │
                             ↓
                    ┌─────────────────┐
                    │   fact_main     │
                    └────────┬────────┘
                             │
                             ↓
                    ┌─────────────────┐
                    │   dim_entity    │
                    └─────────────────┘
```

**Relationships:**
- `fact.column` → `dim.column` (many-to-one)
- Description of relationship

---

## Data Sources

---

### API/Provider Name

**Provider:** Provider name (URL)
**Authentication:** API key / OAuth / etc.
**Rate Limits:** X calls/minute
**Data Coverage:** Geographic/temporal coverage

### API Endpoints Used

| Endpoint | Purpose | Bronze Table | Update Frequency |
|----------|---------|--------------|------------------|
| `/endpoint` | Description | `bronze.table_name` | Daily/Weekly |

### Bronze → Silver Transformation

**Pipeline:** `datapipelines/providers/provider-name/`

```
External API
    ↓
Facets (normalize responses)
    ├─→ FacetName1
    └─→ FacetName2
    ↓
Bronze Storage (partitioned Parquet)
    ├─→ bronze/table1/ (partitioned by date)
    └─→ bronze/table2/ (partitioned by date)
    ↓
BaseModel.build() (YAML-driven transformation)
    ↓
Silver Storage (dimensional model)
    ├─→ silver/model/dims/dim_name/
    └─→ silver/model/facts/fact_name/
```

### Data Quality

- **Completeness:** Description
- **Accuracy:** Description
- **Timeliness:** Description
- **Consistency:** Description

### Expandability

Describe future data sources that could be integrated.

---

## Detailed Schema

---

### Dimensions

#### dim_name

Brief description of the dimension.

**Path:** `storage/silver/model/dims/dim_name`
**Primary Key:** `key_column`
**Grain:** One row per...

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **column1** | type | Description | Example value |
| **column2** | type | Description | Example value |

**Sample Data:**
```
+----------+----------+
| column1  | column2  |
+----------+----------+
| value1   | value2   |
+----------+----------+
```

### Facts

#### fact_name

Brief description of the fact.

**Path:** `storage/silver/model/facts/fact_name`
**Partitions:** `partition_column`
**Grain:** One row per...

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **column1** | type | Description | Example value |
| **column2** | type | Description | Example value |

**Sample Data:**
```
+----------+----------+
| column1  | column2  |
+----------+----------+
| value1   | value2   |
+----------+----------+
```

---

## Graph Structure

---

### Nodes (Tables)

```yaml
graph:
  nodes:
    - id: dim_name
      from: bronze.source_table
      select:
        output_col: input_col
      derive:
        computed_col: "expression"
```

### Edges (Relationships)

```yaml
edges:
  - from: fact_name
    to: dim_name
    on: ["fact_key=dim_key"]
    type: many_to_one
```

### Paths (Materialized Joins)

```yaml
paths:
  - id: view_name
    hops: "fact_name -> dim_name"
    description: "Description"
```

---

## Measures

---

### Simple Aggregations

| Measure | Source | Aggregation | Format | Purpose |
|---------|--------|-------------|--------|---------|
| **measure_name** | table.column | avg/sum/etc | Format | Description |

---

## How-To Guides

---

### How to [Task Name]

**Step 1:** Description

```python
# Code example
```

**Step 2:** Description

```python
# Code example
```

**Step 3:** Description

```python
# Code example
```

---

## Usage Examples

---

### Example 1: [Example Name]

```python
# Complete working example
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Your example code here
```

---

## Design Decisions

---

### Why [Decision]?

**Decision:** What was decided

**Rationale:**
- Reason 1
- Reason 2
- Reason 3

**Trade-offs:** What was traded off

---

## Partitioning Strategy

---

### fact_name

**Partition Column:** `column_name`
**Partition Type:** Date/String/etc
**Partition Format:** `column=value`

**Storage Layout:**
```
storage/silver/model/facts/fact_name/
├── partition=value1/
│   └── part-00000.parquet
└── partition=value2/
    └── part-00000.parquet
```

**Query Optimization:**
- Describe how partitioning improves queries

---

## Related Documentation

---

- [[Related Model 1]] - Description
- [[Related Model 2]] - Description
- [[Architecture Component]] - Description

---

**Tags:** #domain/category #component/model #concept/dimensional-modeling #source/api #status/stable

**Last Updated:** YYYY-MM-DD
**Model Version:** X.Y
**Dependencies:** [[Dependency]]
**Used By:** [[Consumer]]
```

---

## How-To Guide Template

---

Use this template for step-by-step guides.

**File Location:** `docs/guide/1-getting-started/how-to/your-guide-name.md`

```markdown
---
title: "How to [Task Name]"
tags: [type/guide, component/area, concept/topic, status/stable]
aliases: ["Short Name"]
created: YYYY-MM-DD
updated: YYYY-MM-DD
difficulty: beginner|intermediate|advanced
time_required: "XX minutes"
---

# How to [Task Name]

---

> **Brief description of what this guide teaches**

This guide shows you how to [accomplish task]. By the end, you'll be able to [outcome].

---

## Prerequisites

---

Before starting, ensure you have:

- Prerequisite 1
- Prerequisite 2
- Prerequisite 3

**Recommended Reading:**
- [[Related Doc 1]]
- [[Related Doc 2]]

---

## Overview

---

### What You'll Learn

1. Step 1 overview
2. Step 2 overview
3. Step 3 overview

### Estimated Time

**XX minutes** (Y minutes setup, Z minutes implementation)

---

## Step 1: [First Step Name]

---

### Goal

Describe what this step accomplishes.

### Instructions

1. First instruction
2. Second instruction
3. Third instruction

### Code Example

```python
# Complete working code example
```

### Expected Output

```
Expected console output or result
```

### Troubleshooting

**Problem:** Common issue
**Solution:** How to fix it

---

## Step 2: [Second Step Name]

---

### Goal

Describe what this step accomplishes.

### Instructions

1. First instruction
2. Second instruction

### Code Example

```python
# Complete working code example
```

---

## Step 3: [Third Step Name]

---

### Goal

Describe what this step accomplishes.

### Instructions

1. First instruction
2. Second instruction

### Code Example

```python
# Complete working code example
```

---

## Complete Example

---

Here's the complete code from all steps:

```python
# Full working example combining all steps
```

---

## Next Steps

---

Now that you've learned [task], you can:

- Next skill to learn
- Related task to try
- Advanced variation

**Recommended Next:**
- [[Next How-To Guide]]
- [[Related Concept]]

---

## Common Issues

---

### Issue 1: [Problem Description]

**Symptoms:** What you'll see
**Cause:** Why it happens
**Solution:** How to fix it

### Issue 2: [Problem Description]

**Symptoms:** What you'll see
**Cause:** Why it happens
**Solution:** How to fix it

---

## Related Documentation

---

- [[Related Guide 1]]
- [[Architecture Component]]
- [[Model Documentation]]

---

**Tags:** #type/guide #component/area #concept/topic #status/stable

**Last Updated:** YYYY-MM-DD
**Difficulty:** beginner|intermediate|advanced
**Time Required:** XX minutes
```

---

## Architecture Component Template

---

Use this template for architecture documentation.

**File Location:** `docs/guide/3-architecture/components/subsystem/component-name.md`

```markdown
---
title: "[Component Name]"
tags: [type/architecture, component/subsystem, concept/pattern, status/stable]
aliases: ["Short Name"]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# [Component Name]

---

> **Brief one-line description**

Detailed description of the component, its purpose, and role in the system.

**Location:** `/path/to/component/`
**Key Files:** `file1.py`, `file2.py`

---

## Table of Contents

---

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Classes](#key-classes)
- [Data Flow](#data-flow)
- [API Reference](#api-reference)
- [Usage Examples](#usage-examples)
- [Design Patterns](#design-patterns)
- [Extension Points](#extension-points)

---

## Overview

---

### Purpose

What the component does and why it exists.

### Responsibilities

- Responsibility 1
- Responsibility 2
- Responsibility 3

### Dependencies

- Depends on [[Component 1]]
- Depends on [[Component 2]]

### Used By

- [[Consumer 1]]
- [[Consumer 2]]

---

## Architecture

---

### Component Diagram

```
┌─────────────────┐
│   Component A   │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  This Component │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   Component B   │
└─────────────────┘
```

### File Structure

```
component/
├── __init__.py
├── core.py           # Core logic
├── utils.py          # Utilities
└── types.py          # Type definitions
```

---

## Key Classes

---

### ClassName

**File:** `path/to/file.py:XX-YY`

**Purpose:** What this class does

**Key Methods:**
- `method1()` - Description
- `method2()` - Description

**Example:**
```python
# Usage example
```

---

## Data Flow

---

### Flow Diagram

```
Input
  ↓
Process Step 1
  ↓
Process Step 2
  ↓
Output
```

### Description

Narrative description of how data flows through the component.

---

## API Reference

---

### Functions

#### function_name(param1, param2)

**Purpose:** What the function does

**Parameters:**
- `param1` (type): Description
- `param2` (type): Description

**Returns:** Description of return value

**Example:**
```python
result = function_name(value1, value2)
```

---

## Usage Examples

---

### Example 1: [Use Case]

```python
# Complete working example
```

### Example 2: [Use Case]

```python
# Complete working example
```

---

## Design Patterns

---

### Pattern Name

**Pattern:** Factory / Strategy / etc.

**Implementation:** How it's implemented

**Benefits:** Why this pattern was chosen

---

## Extension Points

---

### How to Extend

1. Describe extension point 1
2. Describe extension point 2

### Example Extension

```python
# Example of extending the component
```

---

## Related Documentation

---

- [[Related Component 1]]
- [[Related Component 2]]
- [[Parent Architecture Doc]]

---

**Tags:** #type/architecture #component/subsystem #concept/pattern #status/stable

**Last Updated:** YYYY-MM-DD
**Key Files:** `file1.py`, `file2.py`
```

---

## Usage Tips

---

### For Model Documentation

1. **Start with Schema Overview** - Give readers the big picture first
2. **Move Data Sources Early** - Readers want to know where data comes from
3. **Fix Star Schema Diagrams** - Ensure relationships are accurate
4. **Add How-To Guides** - Include practical walkthroughs
5. **Use Obsidian Features** - Wiki links, tags, frontmatter

### For How-To Guides

1. **One Task Per Guide** - Keep focused on a single goal
2. **Include Complete Examples** - Make sure code actually works
3. **Add Troubleshooting** - Common issues and solutions
4. **Link to Next Steps** - Guide readers to related content

### For Architecture Docs

1. **Diagrams First** - Visual representation before details
2. **File Path References** - Link to actual implementation
3. **Design Patterns** - Explain patterns used
4. **Extension Points** - Show how to extend

### Obsidian Best Practices

1. **Use Wiki Links** - `[[Document Name]]` for cross-references
2. **Add YAML Frontmatter** - Tags, aliases, metadata
3. **Underline Headers** - Use `---` after major sections
4. **Tag Consistently** - Follow [[TAGGING_SYSTEM]]
5. **Add Backlinks** - Link related docs both ways

---

**Tags:** #type/template #type/reference #status/stable

**Last Updated:** 2024-11-08
