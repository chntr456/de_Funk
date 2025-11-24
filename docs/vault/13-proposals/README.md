# Design Proposals

**Architectural proposals and RFCs for de_Funk**

---

## Overview

This section contains design proposals for new features, architectural changes, and technical improvements.

## Proposal Lifecycle

```
Draft → Active → Accepted/Rejected → (Archived)
```

| Status | Directory | Description |
|--------|-----------|-------------|
| **Draft** | `draft/` | Under discussion, open for feedback |
| **Active** | `active/` | Currently being implemented |
| **Accepted** | `accepted/` | Implemented, kept for reference |
| **Rejected** | (deleted or moved) | Not implemented |

---

## Current Proposals

### Accepted (Implemented)

| Proposal | Title | Status | Implemented |
|----------|-------|--------|-------------|
| [BACKEND_ABSTRACTION_STRATEGY](accepted/backend-abstraction-strategy.md) | DuckDB/Spark backend abstraction | Accepted | v1.0 |
| [COMPANY_MODEL_ARCHITECTURE_REVIEW](accepted/company-model-architecture-review.md) | Company model redesign with CIK | Accepted | v2.0 |

### Active (In Progress)

*None currently*

### Draft (Under Discussion)

*None currently*

---

## Proposal Template

When creating a new proposal, use this template:

```markdown
# Proposal: [Title]

**Status**: Draft | Active | Accepted | Rejected
**Author**: [Name]
**Date**: YYYY-MM-DD
**Updated**: YYYY-MM-DD

## Summary

One paragraph summary of the proposal.

## Motivation

Why is this change needed? What problem does it solve?

## Detailed Design

Technical details of the proposed solution.

### Current State

How things work today.

### Proposed Changes

What will change and how.

### Migration Path

How to migrate from current to proposed state.

## Alternatives Considered

What other approaches were considered and why they were rejected.

## Impact

### Benefits

- Benefit 1
- Benefit 2

### Drawbacks

- Drawback 1

### Breaking Changes

List any breaking changes.

## Implementation Plan

1. Step 1
2. Step 2
3. Step 3

## Open Questions

- Question 1?
- Question 2?

## References

- Link 1
- Link 2
```

---

## How to Submit a Proposal

1. **Create draft**: Add markdown file to `draft/` directory
2. **Discuss**: Share with team for feedback
3. **Refine**: Update based on feedback
4. **Move to active**: When implementation starts
5. **Move to accepted**: When complete

---

## Recent History

| Date | Proposal | Action |
|------|----------|--------|
| 2025-11 | Backend Abstraction | Implemented in v1.0 |
| 2025-11 | Company Model Architecture | Implemented in v2.0 |

---

## Related Documentation

- [Architecture](../00-overview/architecture.md) - Current system design
- [Changelog](/CHANGELOG.md) - Version history
