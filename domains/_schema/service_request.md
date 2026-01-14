---
type: schema-template
name: service_request
description: "Canonical schema for 311/service request data (city-agnostic)"
domain: operations
entity: service_request

# Canonical Schema (what Silver looks like)
canonical_schema:
  # Identifiers
  request_id: {type: string, required: true, description: "Unique request identifier"}

  # Temporal
  created_date: {type: timestamp, required: true, description: "Request created date/time"}
  closed_date: {type: timestamp, description: "Request closed date/time"}
  year: {type: int, description: "Year (partition key)"}

  # Request Classification
  request_type: {type: string, required: true, description: "Type of service request"}
  request_category: {type: string, description: "Taxonomy level 1"}
  request_group: {type: string, description: "Taxonomy level 2"}
  short_code: {type: string, description: "Request type short code"}

  # Status
  status: {type: string, description: "Request status (OPEN, CLOSED, etc.)"}

  # Location (text)
  street_address: {type: string, description: "Street address"}
  city: {type: string, description: "City name"}
  zip_code: {type: string, description: "ZIP code"}

  # Geospatial
  latitude: {type: double, description: "Latitude"}
  longitude: {type: double, description: "Longitude"}

  # Geo Keys
  community_area: {type: int, description: "Community area number"}
  ward: {type: int, description: "Ward number"}

  # Metadata
  legacy_record: {type: boolean, description: "From legacy system"}

# Column Mappings
column_mappings:
  request_id: [sr_number, request_id, service_request_id, ticket_id]
  created_date: [created_date, date_created, open_date, request_date]
  closed_date: [closed_date, date_closed, completion_date]
  request_type: [sr_type, request_type, service_type, type]
  short_code: [sr_short_code, short_code, type_code]
  status: [status, request_status, sr_status]
  street_address: [street_address, address, location_address]
  zip_code: [zip_code, zip, postal_code]
  community_area: [community_area, communityarea]
  ward: [ward, ward_number]

# Value Normalization
normalization:
  request_type:
    - uppercase
    - trim
  status:
    - uppercase
    - trim

# Service Request Taxonomy
taxonomy:
  INFRASTRUCTURE:
    STREETS:
      - POTHOLE
      - STREET LIGHT OUT
      - STREET SIGN
      - TRAFFIC SIGNAL
      - PAVEMENT REPAIR
    SIDEWALKS:
      - SIDEWALK REPAIR
      - SIDEWALK INSPECTION
    WATER:
      - WATER MAIN
      - HYDRANT
      - WATER LEAK
    SEWER:
      - SEWER REPAIR
      - SEWER BACKUP
      - CATCH BASIN
    _OTHER: []

  SANITATION:
    GARBAGE:
      - GARBAGE CART
      - MISSED GARBAGE PICKUP
      - BULK PICKUP
    RECYCLING:
      - RECYCLING CART
      - MISSED RECYCLING PICKUP
    DUMPING:
      - ILLEGAL DUMPING
      - FLY DUMPING
    GRAFFITI:
      - GRAFFITI REMOVAL
    _OTHER: []

  TREES:
    TREE_MAINTENANCE:
      - TREE TRIM
      - TREE REMOVAL
      - TREE PLANTING
      - TREE DEBRIS
    _OTHER: []

  BUILDINGS:
    VACANT:
      - VACANT BUILDING
      - VACANT LOT
    CODE_VIOLATION:
      - BUILDING VIOLATION
      - DANGEROUS BUILDING
    _OTHER: []

  RODENT:
    RODENT_CONTROL:
      - RODENT BAITING
      - RAT COMPLAINT
    _OTHER: []

  VEHICLES:
    ABANDONED:
      - ABANDONED VEHICLE
    PARKING:
      - PARKING VIOLATION
    _OTHER: []

  INFORMATION:
    GENERAL:
      - 311 INFORMATION ONLY
      - GENERAL INQUIRY
    _OTHER: []

  _OTHER: []

# Dimension Tables
dimensions:
  dim_request_type:
    description: "Service request type dimension"
    source: fact_service_requests.request_type
    columns:
      request_type_id: {type: string}
      request_type_name: {type: string}
      request_category: {type: string}
      request_group: {type: string}
      short_code: {type: string}

status: active
---

## Service Request Schema Template

City-agnostic schema template for 311/service request data.

### Usage

```yaml
---
type: domain-model
model: chicago_operations
schema_template: _schema/service_request.md
---
```

### Taxonomy Structure

```
request_category (Level 1: INFRASTRUCTURE, SANITATION, etc.)
└── request_group (Level 2: STREETS, GARBAGE, etc.)
    └── request_type (raw, normalized)
```

### Notes

- Handles legacy system data migration (pre-2018 for Chicago)
- Status normalization for consistent reporting
- Response time metrics derived from created_date/closed_date
