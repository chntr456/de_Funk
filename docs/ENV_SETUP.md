# Environment Variable Setup Guide

This guide explains how to set up API keys and other sensitive configuration using environment variables.

## Quick Start

1. **Copy the example file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your API keys**:
   ```bash
   # On Linux/Mac
   nano .env

   # Or use any text editor
   ```

3. **Get your API keys** (see sections below for each provider)

4. **Never commit `.env` to git** (it's already in `.gitignore`)

---

## API Key Setup

### Polygon.io API Keys

**Purpose**: Stock market data (prices, news, company information)

**Get your key**:
1. Go to [https://polygon.io/](https://polygon.io/)
2. Sign up for a free account
3. Navigate to Dashboard > API Keys
4. Copy your API key

**Add to `.env`**:
```bash
POLYGON_API_KEYS=your_polygon_api_key_here
```

**Multiple keys** (for better rate limiting):
```bash
POLYGON_API_KEYS=key1,key2,key3
```

**Rate limits**:
- Free tier: 5 requests/minute
- Starter tier: Higher limits, historical data access
- Multiple keys: Automatically rotated to maximize throughput

---

### Bureau of Labor Statistics (BLS) API Key

**Purpose**: Macroeconomic data (unemployment, inflation, wages, etc.)

**Get your key**:
1. Go to [https://data.bls.gov/registrationEngine/](https://data.bls.gov/registrationEngine/)
2. Register for a free API key
3. Check your email for the key

**Add to `.env`**:
```bash
BLS_API_KEYS=your_bls_api_key_here
```

**Rate limits**:
- Without key: 25 queries/day, 10 years of data per query
- With key: 500 queries/day, 20 years of data per query

**Note**: BLS API is optional. The system will work without it but with reduced rate limits.

---

### Chicago Data Portal API Key

**Purpose**: City of Chicago economic and financial data

**Get your key**:
1. Go to [https://data.cityofchicago.org/](https://data.cityofchicago.org/)
2. Create an account
3. Navigate to your profile > App Tokens
4. Create a new app token

**Add to `.env`**:
```bash
CHICAGO_API_KEYS=your_chicago_app_token_here
```

**Rate limits**:
- Without token: 1,000 requests/day
- With token: Higher limits (varies by plan)

**Note**: Chicago API is optional. The system will work without it but with reduced rate limits.

---

## How It Works

### Architecture

```
┌─────────────────────┐
│   .env file         │  ← You create this (git-ignored)
│   (your API keys)   │
└──────────┬──────────┘
           │
           ├─ Auto-loaded by utils/env_loader.py
           │
           ↓
┌──────────────────────────────────────────────┐
│  Environment Variables                       │
│  (POLYGON_API_KEYS, BLS_API_KEYS, etc.)     │
└──────────┬───────────────────────────────────┘
           │
           ├─ Injected into config by core/context.py
           │
           ↓
┌──────────────────────────────────────────────┐
│  Provider Configs                            │
│  (polygon_cfg, bls_cfg, chicago_cfg)        │
└──────────┬───────────────────────────────────┘
           │
           ├─ Used by ingestors and validators
           │
           ↓
┌──────────────────────────────────────────────┐
│  HTTP Requests to APIs                       │
└──────────────────────────────────────────────┘
```

### Key Files

1. **`.env`** (you create this):
   - Contains your actual API keys
   - Never committed to git (.gitignore)
   - Copy from `.env.example`

2. **`.env.example`**:
   - Template file with all required variables
   - Safe to commit (no actual keys)
   - Documents what keys are needed

3. **`utils/env_loader.py`**:
   - Loads `.env` file automatically
   - Provides helper functions to get API keys
   - Injects credentials into config dictionaries

4. **`core/context.py`**:
   - Loads config JSON files
   - Injects environment variables using env_loader
   - Creates RepoContext with proper credentials

5. **Config JSON files** (`configs/*.json`):
   - No longer contain hardcoded API keys
   - Keys are injected at runtime from environment

---

## Environment vs Config Files

### Before (❌ Insecure):
```json
// configs/polygon_endpoints.json
{
  "credentials": {
    "api_keys": ["hardcoded_key_here"]  ← Committed to git!
  }
}
```

### After (✅ Secure):
```json
// configs/polygon_endpoints.json
{
  "credentials": {
    "api_keys": []  ← Empty, filled from .env at runtime
  }
}
```

```bash
# .env (git-ignored)
POLYGON_API_KEYS=your_actual_key_here
```

---

## Testing Your Setup

### 1. Verify `.env` is loaded:

```python
import os
from utils.env_loader import load_dotenv

# Should auto-load, but you can manually load to check
load_dotenv()

# Check if keys are loaded
print("Polygon keys:", os.getenv('POLYGON_API_KEYS'))
print("BLS keys:", os.getenv('BLS_API_KEYS'))
print("Chicago keys:", os.getenv('CHICAGO_API_KEYS'))
```

### 2. Test with APIValidator:

```python
from core.context import RepoContext
from utils.api_validator import APIValidator

# Load context (automatically injects env vars)
ctx = RepoContext.from_repo_root()

# Test API connection
validator = APIValidator(ctx.polygon_cfg)
is_connected, message = validator.test_api_connection()

print(f"Connected: {is_connected}")
print(f"Message: {message}")
```

### 3. Run a pipeline:

```bash
# Test with a small data pull
python scripts/run_company_data_pipeline.py --days 7 --max-tickers 5
```

---

## Troubleshooting

### "API keys not found" warning

**Problem**: You see a warning about missing API keys

**Solution**:
1. Make sure `.env` exists in the project root
2. Check that variable names match (e.g., `POLYGON_API_KEYS` not `POLYGON_API_KEY`)
3. Ensure no spaces around `=` in `.env` file
4. Restart your Python process to reload environment

### "Invalid API key" error

**Problem**: API returns 401/403 errors

**Solution**:
1. Verify your API key is correct (copy-paste from provider dashboard)
2. Check for extra spaces or quotes in `.env`
3. Some APIs require account activation - check your email
4. For Polygon: Free tier has limited historical data access

### Keys not loading automatically

**Problem**: Environment variables not set even though `.env` exists

**Solution**:
1. The `utils/env_loader.py` module auto-loads on import
2. Make sure you're importing from `core.context` or `utils.env_loader`
3. Check file permissions on `.env` (should be readable)
4. Verify `.env` is in the repository root (same level as `configs/`)

### Multiple projects/environments

**Problem**: Different API keys for dev/staging/production

**Solution**:
1. Use different `.env` files:
   - `.env.dev`
   - `.env.staging`
   - `.env.production`

2. Load the appropriate file:
   ```python
   from utils.env_loader import load_dotenv
   from pathlib import Path

   env = os.getenv('ENVIRONMENT', 'dev')
   load_dotenv(Path(f'.env.{env}'))
   ```

---

## Security Best Practices

### ✅ DO:
- Use `.env` files for local development
- Use environment variables in production (set by hosting platform)
- Rotate API keys periodically
- Use different keys for different environments
- Review `.gitignore` to ensure `.env` is excluded
- Share `.env.example` with your team

### ❌ DON'T:
- Commit `.env` to git
- Share API keys in Slack/email
- Hardcode keys in source code
- Use production keys in development
- Check in files with actual credentials
- Paste keys in screenshots or documentation

---

## CI/CD and Production

### GitHub Actions

```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        env:
          POLYGON_API_KEYS: ${{ secrets.POLYGON_API_KEYS }}
          BLS_API_KEYS: ${{ secrets.BLS_API_KEYS }}
        run: pytest
```

**Add secrets**:
1. Go to your GitHub repo > Settings > Secrets and variables > Actions
2. Add `POLYGON_API_KEYS`, `BLS_API_KEYS`, etc.

### Docker

```dockerfile
# Dockerfile
FROM python:3.9

# Copy code
COPY . /app
WORKDIR /app

# Install dependencies
RUN pip install -r requirements.txt

# Environment variables will be passed at runtime
CMD ["python", "run_full_pipeline.py"]
```

```bash
# Run with environment variables
docker run -e POLYGON_API_KEYS=xxx -e BLS_API_KEYS=yyy myapp
```

### Cloud Platforms

**AWS**: Use AWS Secrets Manager or Parameter Store
**GCP**: Use Secret Manager
**Heroku**: Set via `heroku config:set`
**Azure**: Use Key Vault

---

## Migration Notes

If you're migrating from the old hardcoded system:

1. **Save your existing keys** from `configs/*.json` files
2. **Copy them to `.env`** following the format in `.env.example`
3. **The config files have been updated** to use empty arrays for credentials
4. **No code changes needed** - the new system is backward compatible
5. **Verify** by running the test commands above

**Old keys found**:
- Polygon: `J6tEetTp8m16ZaPw7S2MgV6nHglK14O8`
- Chicago: `3on4vbtla2xwgidykkz7h4q`

These have been removed from the config files and should be added to your `.env`.

---

## Support

**Questions?**
- Check the code: `utils/env_loader.py`
- Review examples: `.env.example`
- File an issue in the repository

**API Documentation**:
- Polygon.io: [https://polygon.io/docs](https://polygon.io/docs)
- BLS API: [https://www.bls.gov/developers/](https://www.bls.gov/developers/)
- Chicago Data Portal: [https://dev.socrata.com/](https://dev.socrata.com/)
