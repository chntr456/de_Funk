# Alpha Vantage Rate Limits

**API throttling and optimization strategies**

---

## Rate Limits by Tier

| Tier | Calls/Minute | Calls/Day | Cost |
|------|--------------|-----------|------|
| **Free** | 5 | 500 | $0 |
| **Premium** | 75 | 60,000+ | Varies |

---

## Free Tier Implications

### Time to Ingest Data

| Tickers | Calls Needed | Time (Free Tier) |
|---------|--------------|------------------|
| 10 | 20 (ref + prices) | 4 minutes |
| 100 | 200 | 40 minutes |
| 500 | 1,000 | 3.3 hours |
| 1,000 | 2,000 | 6.7 hours |

**Formula**: `time_minutes = (tickers * 2) / 5`

### Daily Limit Impact

With 500 calls/day:
- Maximum 250 tickers (reference + prices)
- Must plan ingestion across multiple days

---

## de_Funk Rate Limiting

### Configuration

```json
// configs/alpha_vantage_endpoints.json
{
  "rate_limit": {
    "calls_per_second": 1.0
  }
}
```

**Note**: Configured at 1.0 calls/sec (below 5/min limit) for safety margin.

### Implementation

```python
# datapipelines/providers/alpha_vantage/alpha_vantage_ingestor.py

class AlphaVantageIngestor:
    def _fetch_calls(self, calls, response_key=None):
        results = []
        for call in calls:
            # Rate limiting enforced here
            result = self._make_request(call)
            results.append(result)
            time.sleep(1.0)  # 1 second between calls
        return results
```

---

## Optimization Strategies

### 1. Use Bulk Endpoints

The `LISTING_STATUS` endpoint returns **ALL tickers in one call**:

```python
# One API call for all tickers!
response = client.get("LISTING_STATUS", state="active")
# Returns CSV with 10,000+ tickers
```

**Savings**: Instead of 10,000+ calls, use 1 call for ticker discovery.

### 2. Prioritize High-Value Tickers

```python
# Ingest top N by market cap or volume
python -m scripts.ingest.run_full_pipeline --top-n 100
```

### 3. Incremental Updates

Only fetch new data, not full history:

```python
# Fetch only recent data (compact = 100 days)
facet = SecuritiesPricesFacetAV(
    spark,
    tickers=['AAPL'],
    output_size='compact'  # Not 'full' (20+ years)
)
```

### 4. Cache Responses

Reference data changes infrequently:

```python
# Fetch OVERVIEW monthly, not daily
# Company fundamentals rarely change
```

### 5. Parallel with Premium

Premium tier allows concurrent requests:

```python
# Only for premium tier (75 calls/min)
with ThreadPoolExecutor(max_workers=5) as executor:
    results = executor.map(fetch_ticker, tickers)
```

---

## Error Handling

### Rate Limit Response

```json
{
  "Note": "Thank you for using Alpha Vantage! Our standard API call frequency is 5 calls per minute..."
}
```

### Detection

```python
def is_rate_limited(response):
    if "Note" in response:
        return "API call frequency" in response["Note"]
    return False
```

### Recovery

```python
def fetch_with_backoff(call, max_retries=3):
    for attempt in range(max_retries):
        result = make_request(call)
        if is_rate_limited(result):
            wait_time = 60 * (2 ** attempt)  # 60, 120, 240 seconds
            time.sleep(wait_time)
            continue
        return result
    raise RateLimitError("Exceeded retries")
```

---

## Monitoring

### Track API Usage

```python
# Log each API call
logger.info(f"API call {call_count}/{500} today: {endpoint}")

# Alert at 80% usage
if call_count >= 400:
    logger.warning("Approaching daily API limit!")
```

### Estimate Time

```python
def estimate_completion(remaining_tickers, calls_per_ticker=2):
    calls_needed = remaining_tickers * calls_per_ticker
    minutes_needed = calls_needed / 5  # Free tier
    return f"{minutes_needed:.0f} minutes"
```

---

## Premium Upgrade Considerations

### When to Upgrade

Consider premium if you need:
- More than 250 tickers daily
- Faster ingestion (hours → minutes)
- Commercial use
- Higher reliability

### Cost-Benefit

| Scenario | Free Tier | Premium |
|----------|-----------|---------|
| 100 tickers | 40 min/day | 3 min/day |
| 1,000 tickers | Not feasible | 27 min/day |
| Real-time updates | Not practical | Feasible |

---

## Related Documentation

- [Terms of Use](terms-of-use.md) - Usage restrictions
- [API Reference](api-reference.md) - Endpoints
- [Facets](facets.md) - Data transformations
