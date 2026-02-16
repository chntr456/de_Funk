---
type: data-source
source: listing_status
bronze_table: alpha_vantage/listing_status
description: "All US-listed securities from LISTING_STATUS endpoint (~12,499 tickers)"
update_frequency: daily
feeds: [securities_master, stocks]
---

## Listing Status

All active and delisted US securities. Primary source for the securities master dimension.
