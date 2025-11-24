# Alpha Vantage Terms of Use

**Usage restrictions and licensing for Alpha Vantage data**

---

## Summary

| Aspect | Restriction |
|--------|-------------|
| **Commercial Use** | **NOT PERMITTED** (free tier) |
| **Attribution** | Required |
| **Redistribution** | Not permitted |
| **Data Storage** | Permitted for personal/educational use |

---

## Key Restrictions

### No Commercial Use (Free Tier)

The free API tier is licensed for **personal, educational, and non-commercial use only**.

**You MAY NOT:**
- Use data in commercial applications
- Sell or monetize Alpha Vantage data
- Use data for commercial trading systems
- Redistribute data to third parties

**You MAY:**
- Use for personal research
- Use for educational projects
- Store data locally for analysis
- Build non-commercial tools

### Premium Tier

Commercial use requires a **premium subscription**. Contact Alpha Vantage for commercial licensing.

---

## Attribution Requirements

When displaying Alpha Vantage data, you must include attribution:

> Data provided by Alpha Vantage (https://www.alphavantage.co/)

---

## API Usage Guidelines

### Rate Limits

| Tier | Calls/Minute | Calls/Day |
|------|--------------|-----------|
| Free | 5 | 500 |
| Premium | 75 | 60,000+ |

**Enforcement**: Exceeding limits returns error messages:

```json
{
    "Note": "Thank you for using Alpha Vantage! Our standard API call frequency is 5 calls per minute and 500 calls per day."
}
```

### Fair Use

- Do not abuse the API with excessive requests
- Implement proper rate limiting in your code
- Cache responses where appropriate
- Use bulk endpoints when available (e.g., LISTING_STATUS)

---

## Data Accuracy Disclaimer

Alpha Vantage provides data "as is" without warranty:

- Data may contain errors or omissions
- Historical data may be adjusted
- Real-time quotes may be delayed
- Verify critical data from primary sources

---

## Compliance Checklist

Before using Alpha Vantage data, ensure:

- [ ] You are not using data commercially (free tier)
- [ ] You include attribution where data is displayed
- [ ] You implement rate limiting (5 calls/min free)
- [ ] You do not redistribute data to third parties
- [ ] You understand data accuracy limitations

---

## Legal Reference

Full terms available at:
- [Alpha Vantage Terms of Service](https://www.alphavantage.co/terms_of_service/)
- [Alpha Vantage Support](https://www.alphavantage.co/support/)

---

## Implementation Notes

### de_Funk Compliance

The de_Funk project implements Alpha Vantage with:

1. **Rate limiting**: `1.0 calls/sec` configured in `alpha_vantage_endpoints.json`
2. **Local storage**: Data stored in Bronze/Silver layers for analysis
3. **No redistribution**: Data not exposed via public APIs
4. **Personal/Educational use**: Framework designed for learning

### Configuration

```json
// configs/alpha_vantage_endpoints.json
{
  "base_urls": {
    "core": "https://www.alphavantage.co"
  },
  "rate_limit": {
    "calls_per_second": 1.0
  }
}
```

---

## Contact

For commercial licensing inquiries:
- Website: https://www.alphavantage.co/premium/
- Email: support@alphavantage.co

---

## Related Documentation

- [Overview](overview.md) - Provider capabilities
- [Rate Limits](rate-limits.md) - Throttling strategies
- [API Reference](api-reference.md) - Endpoint details
