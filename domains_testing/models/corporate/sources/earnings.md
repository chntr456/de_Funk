---
type: domain-model-source
source: earnings
extends: _base.corporate.earnings
maps_to: fact_earnings
from: bronze.alpha_vantage_earnings

aliases:
  - [earnings_id, TBD]
  - [entity_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]
  - [report_date_id, "CAST(REGEXP_REPLACE(CAST(reportedDate AS STRING), '-', '') AS INT)"]
  - [fiscal_date_ending, fiscalDateEnding]
  - [reported_eps, reportedEPS]
  - [estimated_eps, estimatedEPS]
  - [surprise_eps, surprise]
  - [surprise_percentage, surprisePercentage]
---

## Earnings
Quarterly reported EPS, estimated EPS, and surprise metrics.
