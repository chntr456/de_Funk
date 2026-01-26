# Chicago Data Portal Terms of Use

**Usage terms for City of Chicago open data**

---

## Summary

| Aspect | Status |
|--------|--------|
| **Commercial Use** | **PERMITTED** |
| **Attribution** | Recommended |
| **Redistribution** | Permitted |
| **Data Modification** | Prohibited (alteration of meaning) |
| **Cost** | Free |

---

## Official Terms

The Chicago Data Portal provides open data under the City of Chicago's Open Data Policy. Data is released under open terms similar to Creative Commons.

### Key Points

1. **Free to Use**: All data freely available without charge
2. **Commercial OK**: You may use data for commercial purposes
3. **Redistribution OK**: You may share and redistribute data
4. **Derivative Works OK**: You may create derived products

---

## Important Restrictions

### No Intent to Alter or Misrepresent

**You must NOT alter data in ways that misrepresent the original information.**

> "Users may not use data in a manner that falsely implies City endorsement or misrepresents the data."

**Examples of prohibited alterations**:
- Changing permit data to show different outcomes
- Modifying unemployment figures
- Creating false statistics attributed to the City
- Implying City endorsement of analysis

**Permitted uses**:
- Aggregating data
- Creating visualizations
- Combining with other data sources
- Building applications

---

## Attribution Guidelines

While not legally required, the City recommends attribution:

> Data provided by the City of Chicago Data Portal (https://data.cityofchicago.org)

### Citation Format

```
City of Chicago. [Dataset Name]. Chicago Data Portal.
Retrieved from https://data.cityofchicago.org/d/[dataset-id]
```

Example:
```
City of Chicago. Unemployment by Community Area. Chicago Data Portal.
Retrieved from https://data.cityofchicago.org/d/ane4-dwhs
```

---

## API Terms (Socrata)

The Chicago Data Portal uses the Socrata Open Data API (SODA).

### App Token

- **Without Token**: 1,000 requests/day
- **With Token**: Higher limits (varies)

Get token at: https://data.cityofchicago.org/profile/app_tokens

### Fair Use

- Implement rate limiting
- Cache responses appropriately
- Use pagination for large datasets
- Don't overwhelm the API with requests

---

## Data Accuracy Disclaimer

The City provides data "as is":

- Data may contain errors
- Some data is user-reported
- Historical data may be corrected
- Not all records may be complete

### Data Quality Notes

| Dataset | Quality Notes |
|---------|---------------|
| Building Permits | Generally reliable, some delays |
| Business Licenses | Updated regularly |
| Unemployment | Estimates, may be revised |
| Crime Data | Preliminary, subject to revision |

---

## Compliance Checklist

- [ ] You are NOT misrepresenting or altering data meaning
- [ ] You are NOT implying City endorsement
- [ ] You understand data may have quality issues
- [ ] You've implemented appropriate rate limiting
- [ ] You attribute the City as data source (recommended)

---

## Legal Reference

- [Chicago Open Data Policy](https://www.chicago.gov/city/en/narr/foia/open_data.html)
- [Socrata Terms of Service](https://dev.socrata.com/docs/tos.html)
- [Data Portal Terms](https://data.cityofchicago.org/site/site-terms-of-use)

---

## de_Funk Implementation

### Compliance Measures

1. **No Alteration**: Raw data stored in Bronze without modification
2. **Attribution**: Data source documented in metadata
3. **Rate Limiting**: Configured at 5 calls/sec (with token)
4. **Caching**: Data cached locally

### Configuration

```json
// configs/chicago_endpoints.json
{
  "base_urls": {
    "core": "https://data.cityofchicago.org"
  },
  "rate_limit": {
    "calls_per_second": 5.0
  }
}
```

---

## Contact

- Data Portal: https://data.cityofchicago.org
- Open Data Team: dataportal@cityofchicago.org
- Technical Support: https://support.socrata.com

---

## Related Documentation

- [Overview](overview.md) - Provider capabilities
- [API Reference](api-reference.md) - Socrata endpoints
