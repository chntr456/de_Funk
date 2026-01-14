---
type: api-provider
provider_id: bls
provider: Bureau of Labor Statistics
api_type: rest
category: federal
base_url: https://api.bls.gov/publicAPI/v2
homepage: https://www.bls.gov/developers/
auth_model: api-key
env_api_key: BLS_API_KEYS
data_domains: [labor, employment, economic]
data_tags: [public, time-series, economic-indicators, federal]
models: [macro]
status: active
rate_limit_per_sec: 0.42
bulk_download: false
last_verified:
last_reviewed:
notes: "Register at https://data.bls.gov/registrationEngine/ for API key"
---

## Description

The Bureau of Labor Statistics (BLS) provides economic data including unemployment rates, employment statistics, consumer price index (CPI), producer price index (PPI), productivity metrics, and wage data.

**API Version**: v2 (requires registration for higher limits and additional features)

**Key Data Series**:
- **Unemployment**: LNS14000000 - Civilian Labor Force Unemployment Rate
- **Employment**: CES0000000001 - Total Nonfarm Employment
- **CPI**: CUUR0000SA0 - Consumer Price Index All Urban Consumers
- **PPI**: WPUFD4 - Producer Price Index Final Demand
- **Wages**: CES0500000003 - Average Hourly Earnings Total Private
- **Job Openings**: JTS00000000JOL - JOLTS Job Openings Total Nonfarm
- **Quits Rate**: JTS00000000QUR - JOLTS Quits Rate Total Nonfarm

## Rate Limits

| Tier | Daily Limit | Years per Query | Features |
|------|-------------|-----------------|----------|
| Unregistered | 25 queries | 10 years | Basic data |
| v1 Registered | 500 queries | 10 years | Basic data |
| v2 Registered | 500 queries | 20 years | Net/percent calculations, annual averages |

## Homelab Usage Notes

```bash
# Ingest unemployment and CPI data
python -m scripts.ingest.run_bls_ingestion --series unemployment cpi --years 5

# Full macro indicator refresh
python -m scripts.ingest.run_bls_ingestion --all-series --years 10
```

**Recommended Schedule**: Weekly refresh (data is mostly monthly)

## Known Quirks

1. **POST for timeseries**: The main data endpoint requires POST with JSON body
2. **Series ID format**: IDs are cryptic strings - maintain a lookup table
3. **Monthly release schedule**: Most data released on specific days each month
4. **Seasonal adjustment**: Many series have SA (seasonally adjusted) and NSA variants
5. **Revision lag**: Initial releases are revised in subsequent months
