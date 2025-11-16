# Pipeline Testing

**Testing data pipelines and ingestion**

Script: `scripts/test_pipeline_e2e.py`

---

## Overview

Pipeline testing validates the **Bronze → Silver data flow** and ensures data quality through the ingestion pipeline.

---

## Test Levels

### Unit Tests (Facets)

```python
def test_facet_normalization():
    """Test facet normalizes raw JSON correctly."""
    raw_data = [{"o": 150, "h": 155, "c": 152}]

    facet = PricesDailyFacet(spark)
    df = facet.normalize([raw_data])

    assert 'open' in df.columns
    assert df.select('open').first()[0] == 150.0
```

---

### Integration Tests (Ingestors)

```python
def test_ingestor_writes_bronze():
    """Test ingestor writes to Bronze layer."""
    ingestor = PolygonIngestor(spark, api_keys, storage_router)
    ingestor.run(tickers=['TEST'], date_from='2024-01-01')

    # Verify Bronze data exists
    bronze_path = storage_router.bronze_path('polygon_daily_prices')
    df = spark.read.parquet(bronze_path)
    assert df.count() > 0
```

---

### End-to-End Tests

```bash
python scripts/test_pipeline_e2e.py
```

**Validates**:
1. API fetching
2. Facet normalization
3. Bronze write
4. Model build
5. Silver query

---

## Data Quality Tests

```python
def test_data_quality():
    """Test Bronze data meets quality standards."""
    df = spark.read.parquet(bronze_path)

    # No nulls in required columns
    assert df.filter(col('ticker').isNull()).count() == 0

    # Valid date range
    assert df.filter(col('trade_date') < '2020-01-01').count() == 0

    # Positive prices
    assert df.filter(col('close') <= 0).count() == 0
```

---

## Related Documentation

- [Pipeline Architecture](../04-data-pipelines/pipeline-architecture.md)
- [Facet System](../04-data-pipelines/facet-system.md)
- [Testing Guide](testing-guide.md)
