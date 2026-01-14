---
type: schema-reference
schema: fbi_ucr_codes
version: 1.0
description: "FBI Uniform Crime Reporting (UCR) code taxonomy"

# FBI UCR Program Overview
# Part I (Index) crimes are reported nationally for crime statistics
# Part II crimes are all other offenses

# Reference
source: "FBI UCR Program - https://ucr.fbi.gov/"
notes: "Stable taxonomy used nationwide. Codes may appear as numeric or alpha in source data."

# Code Taxonomy
codes:
  # Part I - Violent Crimes (crimes against persons)
  part_i_violent:
    "01A": {name: "Homicide - 1st & 2nd Degree Murder", category: "VIOLENT", subcategory: "HOMICIDE"}
    "01B": {name: "Homicide - Involuntary Manslaughter", category: "VIOLENT", subcategory: "HOMICIDE"}
    "02":  {name: "Criminal Sexual Assault", category: "VIOLENT", subcategory: "SEXUAL_ASSAULT"}
    "03":  {name: "Robbery", category: "VIOLENT", subcategory: "ROBBERY"}
    "04A": {name: "Aggravated Assault", category: "VIOLENT", subcategory: "ASSAULT"}
    "04B": {name: "Aggravated Battery", category: "VIOLENT", subcategory: "ASSAULT"}
    "08A": {name: "Simple Assault", category: "VIOLENT", subcategory: "ASSAULT"}
    "08B": {name: "Simple Battery", category: "VIOLENT", subcategory: "ASSAULT"}

  # Part I - Property Crimes (crimes against property)
  part_i_property:
    "05":  {name: "Burglary", category: "PROPERTY", subcategory: "BURGLARY"}
    "06":  {name: "Larceny-Theft", category: "PROPERTY", subcategory: "THEFT"}
    "07":  {name: "Motor Vehicle Theft", category: "PROPERTY", subcategory: "VEHICLE_THEFT"}
    "09":  {name: "Arson", category: "PROPERTY", subcategory: "ARSON"}

  # Part II - Other Offenses
  part_ii:
    "10":  {name: "Forgery & Counterfeiting", category: "FINANCIAL", subcategory: "FORGERY"}
    "11":  {name: "Fraud", category: "FINANCIAL", subcategory: "FRAUD"}
    "12":  {name: "Embezzlement", category: "FINANCIAL", subcategory: "EMBEZZLEMENT"}
    "13":  {name: "Stolen Property", category: "PROPERTY", subcategory: "STOLEN_PROPERTY"}
    "14":  {name: "Vandalism", category: "PROPERTY", subcategory: "VANDALISM"}
    "15":  {name: "Weapons Violation", category: "PUBLIC_ORDER", subcategory: "WEAPONS"}
    "16":  {name: "Prostitution", category: "PUBLIC_ORDER", subcategory: "PROSTITUTION"}
    "17":  {name: "Sex Offense", category: "PUBLIC_ORDER", subcategory: "SEX_OFFENSE"}
    "18":  {name: "Drug Abuse", category: "DRUG", subcategory: "NARCOTICS"}
    "19":  {name: "Gambling", category: "PUBLIC_ORDER", subcategory: "GAMBLING"}
    "20":  {name: "Offenses Against Family", category: "PUBLIC_ORDER", subcategory: "FAMILY"}
    "22":  {name: "Liquor Laws", category: "PUBLIC_ORDER", subcategory: "LIQUOR"}
    "24":  {name: "Disorderly Conduct", category: "PUBLIC_ORDER", subcategory: "DISORDERLY"}
    "26":  {name: "Other Offense", category: "OTHER", subcategory: "OTHER"}

# Schema for dim_fbi_code dimension
schema:
  columns:
    fbi_code: {type: string, required: true, description: "FBI UCR code"}
    fbi_code_name: {type: string, description: "Code description"}
    part: {type: string, description: "Part I (Index) or Part II"}
    is_index_crime: {type: boolean, description: "Part I crime (reported nationally)"}
    is_violent: {type: boolean, description: "Crime against persons"}
    category: {type: string, description: "Top-level taxonomy category"}
    subcategory: {type: string, description: "Second-level taxonomy"}

# Mapping Notes
mapping_notes: |
  Chicago crime data includes `fbi_code` directly in records.
  Some codes may appear with/without leading zeros (e.g., "6" vs "06").

  Normalization:
  - Pad numeric codes to 2 digits: "6" -> "06"
  - Handle letter suffixes: "01A", "04B", "08A"

  Example:
    SELECT LPAD(REGEXP_REPLACE(fbi_code, '[^0-9]', ''), 2, '0') ||
           COALESCE(REGEXP_EXTRACT(fbi_code, '[A-Z]$'), '') as normalized_fbi_code
---

## FBI Uniform Crime Reporting (UCR) Codes

### Overview

The FBI UCR Program collects crime statistics nationwide. Crimes are divided into:

**Part I (Index) Crimes** - Major crimes tracked for national statistics:
- Violent: Homicide, Sexual Assault, Robbery, Aggravated Assault
- Property: Burglary, Larceny-Theft, Motor Vehicle Theft, Arson

**Part II Crimes** - All other offenses

### Taxonomy

```
VIOLENT
├── HOMICIDE (01A, 01B)
├── SEXUAL_ASSAULT (02)
├── ROBBERY (03)
└── ASSAULT (04A, 04B, 08A, 08B)

PROPERTY
├── BURGLARY (05)
├── THEFT (06)
├── VEHICLE_THEFT (07)
├── ARSON (09)
├── STOLEN_PROPERTY (13)
└── VANDALISM (14)

FINANCIAL
├── FORGERY (10)
├── FRAUD (11)
└── EMBEZZLEMENT (12)

DRUG
└── NARCOTICS (18)

PUBLIC_ORDER
├── WEAPONS (15)
├── PROSTITUTION (16)
├── SEX_OFFENSE (17)
├── GAMBLING (19)
├── FAMILY (20)
├── LIQUOR (22)
└── DISORDERLY (24)

OTHER (26)
```

### Usage with Chicago Data

Chicago crime records include both IUCR (state) and FBI (federal) codes:

```sql
-- Join crimes to FBI taxonomy
SELECT
    c.*,
    f.fbi_code_name,
    f.category,
    f.is_index_crime
FROM chicago_public_safety.fact_crimes c
LEFT JOIN foundation.dim_fbi_code f
    ON UPPER(TRIM(c.fbi_code)) = f.fbi_code;
```

### Data Source

FBI UCR Program: https://ucr.fbi.gov/

Crime Data Explorer API (if needed): https://crime-data-explorer.fr.cloud.gov/pages/docApi
