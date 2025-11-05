# Implemented Models

This directory contains all implemented data models for the de_Funk platform.

## Directory Structure

```
models/implemented/
├── core/              # Shared dimensions (calendar, etc.)
├── company/           # Company financial data model
├── forecast/          # Time series forecast model
├── city_finance/      # Municipal finance model (Chicago data)
└── macro/             # Macroeconomic indicators model (BLS data)
```

## Model Overview

### Core Model
**Purpose:** Shared dimensions and reference data used by all other models
**Key Table:** `dim_calendar` with 27 comprehensive date attributes
**Dependencies:** None (foundation model)

### Company Model
**Purpose:** Company financial and market data
**Key Tables:** `dim_company`, `fact_prices`, `fact_news`
**Dependencies:** `core`
**Data Source:** Polygon.io API

### Forecast Model
**Purpose:** Time series forecasting
**Key Tables:** `fact_forecasts`, `fact_forecast_accuracy`
**Dependencies:** `core`, `company`

### Macro Model
**Purpose:** Macroeconomic indicators (BLS data)
**Key Tables:** `fact_unemployment`, `fact_cpi`, `fact_employment`
**Dependencies:** `core`
**Data Source:** BLS API

### City Finance Model
**Purpose:** Municipal finance (Chicago data)
**Key Tables:** `fact_local_unemployment`, `dim_community_area`
**Dependencies:** `core`, `macro`
**Data Source:** Chicago Data Portal

## Architecture

All models inherit from `BaseModel` which provides:
- Generic graph building from YAML configuration
- Automatic table discovery and metadata
- Cross-model dependencies via session injection
- Connection abstraction (Spark or DuckDB)

## Creating a New Model

See main documentation for creating new models.
All models follow the same pattern: YAML config + minimal Python class.
