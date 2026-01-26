# BLS Terms of Use

**Usage terms for Bureau of Labor Statistics data**

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

The Bureau of Labor Statistics (BLS) is a U.S. federal government agency. As such, its data is **public domain** under U.S. law.

### Key Points

1. **Free to Use**: All BLS data is freely available without charge
2. **No Copyright**: Government data is not subject to copyright
3. **Commercial OK**: You may use data for commercial purposes
4. **Redistribution OK**: You may share and redistribute data

---

## Important Restrictions

### No Intent to Alter

**You must NOT alter data in ways that misrepresent the original information.**

> "BLS data must be used in a manner that does not alter the meaning or intent of the original data."

**Examples of prohibited alterations**:
- Changing unemployment rates
- Modifying CPI values
- Misrepresenting data sources
- Creating false statistics attributed to BLS

**Permitted uses**:
- Aggregating data
- Calculating derived statistics
- Adjusting for inflation using CPI
- Combining with other data sources

---

## Attribution Guidelines

While not legally required, BLS recommends attribution:

> Data provided by the U.S. Bureau of Labor Statistics (https://www.bls.gov)

### Citation Format

```
U.S. Bureau of Labor Statistics. [Series Name]. Retrieved from https://www.bls.gov
```

Example:
```
U.S. Bureau of Labor Statistics. Unemployment Rate (LNS14000000).
Retrieved from https://data.bls.gov/timeseries/LNS14000000
```

---

## API Usage Terms

### Registration

- **Unregistered**: 25 queries/day, 10 years of data
- **Registered**: 500 queries/day, 20 years of data

Registration is free at: https://data.bls.gov/registrationEngine/

### Fair Use

- Do not abuse API with excessive requests
- Implement rate limiting in applications
- Cache responses when appropriate
- Use batch requests for multiple series

---

## Data Accuracy Disclaimer

BLS provides data "as is":

- Data may be revised after initial publication
- Seasonal adjustments may change
- Historical data may be benchmarked
- Verify critical data from official releases

### Revision Schedule

| Data Type | Revision Frequency |
|-----------|-------------------|
| Employment | Monthly (preliminary → final) |
| CPI | Monthly (preliminary → final) |
| Unemployment | Monthly with annual benchmark |

---

## Compliance Checklist

- [ ] You are NOT altering data to misrepresent meaning
- [ ] You understand data may be revised
- [ ] You've implemented appropriate rate limiting
- [ ] You attribute BLS as data source (recommended)

---

## Legal Reference

- [BLS Information and Copyright Policy](https://www.bls.gov/bls/linksite.htm)
- [Data.gov Open Data Policy](https://www.data.gov/open-gov/)
- [BLS API Terms](https://www.bls.gov/developers/api_signature_v2.htm)

---

## de_Funk Implementation

### Compliance Measures

1. **No Alteration**: Raw data stored in Bronze without modification
2. **Attribution**: Data source documented in metadata
3. **Rate Limiting**: Configured at 0.42 calls/sec
4. **Caching**: Data cached locally to minimize API calls

### Configuration

```json
// configs/bls_endpoints.json
{
  "base_urls": {
    "core": "https://api.bls.gov/publicAPI/v2"
  },
  "rate_limit": {
    "calls_per_second": 0.42
  }
}
```

---

## Contact

- Website: https://www.bls.gov
- API Support: https://www.bls.gov/developers/
- General: https://www.bls.gov/bls/contact.htm

---

## Related Documentation

- [Overview](overview.md) - Provider capabilities
- [API Reference](api-reference.md) - Endpoints and series IDs
