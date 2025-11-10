#!/usr/bin/env python3
"""
Standalone test script for forecast view creation.
Runs outside Streamlit to isolate the issue.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("FORECAST VIEW STANDALONE TEST")
print("=" * 80)

# Step 1: Initialize repo context
print("\n[1] Initializing repository context...")
try:
    from core.context import RepoContext
    ctx = RepoContext.from_repo_root(connection_type="duckdb")
    print("✓ Context initialized")
    print(f"  - Connection type: {type(ctx.connection)}")
    print(f"  - Repo root: {ctx.repo}")
except Exception as e:
    print(f"✗ Failed to initialize context: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 2: Create session
print("\n[2] Creating UniversalSession...")
try:
    from models.api.session import UniversalSession
    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )
    print("✓ Session created")
    print(f"  - Session type: {type(session)}")
    print(f"  - Has model_graph: {hasattr(session, 'model_graph')}")
except Exception as e:
    print(f"✗ Failed to create session: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 3: Load forecast model (should trigger session injection)
print("\n[3] Loading forecast model...")
print("-" * 80)
try:
    forecast_model = session.load_model('forecast')
    print("-" * 80)
    print("✓ Forecast model loaded")
    print(f"  - Model type: {type(forecast_model)}")
    print(f"  - Model class: {forecast_model.__class__.__name__}")
    print(f"  - Has set_session attr: {hasattr(forecast_model, 'set_session')}")
    print(f"  - Has session attr: {hasattr(forecast_model, 'session')}")
    if hasattr(forecast_model, 'session'):
        print(f"  - session is None: {forecast_model.session is None}")
        if forecast_model.session:
            print(f"  - session type: {type(forecast_model.session)}")
except Exception as e:
    print("-" * 80)
    print(f"✗ Failed to load forecast model: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 4: Build forecast model (triggers register_views)
print("\n[4] Building forecast model (triggers register_views)...")
print("-" * 80)
try:
    forecast_model.ensure_built()
    print("-" * 80)
    print("✓ Forecast model built")

    if hasattr(forecast_model, '_facts'):
        print(f"  - _facts keys: {list(forecast_model._facts.keys())}")
        print(f"  - Has vw_price_predictions: {'vw_price_predictions' in forecast_model._facts}")
    else:
        print(f"  - No _facts attribute")

except Exception as e:
    print("-" * 80)
    print(f"✗ Failed to build forecast model: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 5: Try to access the view
print("\n[5] Testing view access...")
try:
    if 'vw_price_predictions' in forecast_model._facts:
        view = forecast_model._facts['vw_price_predictions']
        print(f"✓ View accessible from _facts")
        print(f"  - View type: {type(view)}")

        # Try to query it
        try:
            # Get sample data
            if hasattr(view, 'limit'):
                sample = view.limit(5)
                print(f"  - View is queryable via .limit()")

                # Show schema
                if hasattr(sample, 'columns'):
                    print(f"  - Columns: {sample.columns}")

                # Fetch data
                if hasattr(sample, 'df'):
                    df = sample.df()
                    print(f"  - Sample rows: {len(df)}")
                    if len(df) > 0:
                        print(f"  - First row: {df.iloc[0].to_dict()}")

        except Exception as e:
            print(f"  ⚠ Could not query view: {e}")
    else:
        print(f"✗ View not in _facts")

except Exception as e:
    print(f"✗ Failed to access view: {e}")
    import traceback
    traceback.print_exc()

# Step 6: Try to load company model directly
print("\n[6] Testing company model access...")
try:
    company_model = session.load_model('company')
    print("✓ Company model loaded")

    company_model.ensure_built()
    print("✓ Company model built")

    if hasattr(company_model, '_facts'):
        print(f"  - Company _facts keys: {list(company_model._facts.keys())}")
        print(f"  - Has fact_prices: {'fact_prices' in company_model._facts}")

        if 'fact_prices' in company_model._facts:
            fact_prices = company_model._facts['fact_prices']
            print(f"  - fact_prices type: {type(fact_prices)}")

            # Try to query it
            try:
                if hasattr(fact_prices, 'limit'):
                    sample = fact_prices.limit(5)
                    if hasattr(sample, 'df'):
                        df = sample.df()
                        print(f"  - fact_prices has {len(df)} sample rows")
            except Exception as e:
                print(f"  ⚠ Could not query fact_prices: {e}")
    else:
        print(f"  - Company model has no _facts")

except Exception as e:
    print(f"✗ Failed to load company model: {e}")
    import traceback
    traceback.print_exc()

# Step 7: Check if view exists in DuckDB catalog
print("\n[7] Checking DuckDB catalog for view...")
try:
    if hasattr(forecast_model, 'connection'):
        conn = forecast_model.connection
        if hasattr(conn, 'conn'):
            duckdb_conn = conn.conn
        else:
            duckdb_conn = conn

        # Query information_schema
        views_df = duckdb_conn.execute("""
            SELECT schema_name, view_name
            FROM information_schema.views
            WHERE schema_name = 'forecast'
        """).fetchdf()

        print(f"✓ Views in forecast schema: {list(views_df['view_name'])}")

        if 'vw_price_predictions' in views_df['view_name'].values:
            print(f"✓ vw_price_predictions exists in catalog")

            # Try to query it directly
            try:
                result = duckdb_conn.execute(
                    "SELECT * FROM forecast.vw_price_predictions LIMIT 5"
                ).fetchdf()
                print(f"✓ View is queryable via SQL")
                print(f"  - Columns: {list(result.columns)}")
                print(f"  - Rows: {len(result)}")
                if len(result) > 0:
                    print(f"  - Sample row:")
                    for col, val in result.iloc[0].items():
                        print(f"      {col}: {val}")
            except Exception as e:
                print(f"⚠ Could not query view via SQL: {e}")
        else:
            print(f"✗ vw_price_predictions NOT in catalog")

except Exception as e:
    print(f"✗ Failed to check catalog: {e}")
    import traceback
    traceback.print_exc()

# Step 8: Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

checks = []
checks.append(("Session created", True))
checks.append(("Forecast model loaded", forecast_model is not None))
checks.append(("Session injected", hasattr(forecast_model, 'session') and forecast_model.session is not None))
checks.append(("Model built", hasattr(forecast_model, '_is_built') and forecast_model._is_built))
checks.append(("View in _facts", hasattr(forecast_model, '_facts') and 'vw_price_predictions' in forecast_model._facts))

for check_name, passed in checks:
    status = "✓" if passed else "✗"
    print(f"{status} {check_name}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
