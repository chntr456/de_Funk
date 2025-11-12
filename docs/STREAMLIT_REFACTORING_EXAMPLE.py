"""
Example Implementation: Refactored NotebookSession._get_weighted_aggregate_data()

This file shows the exact code changes needed to integrate the unified measure framework
into the Streamlit app's NotebookSession class.

Location to update: app/notebook/api/notebook_session.py (lines 345-448)
"""

import pandas as pd
from typing import Any, Dict
from app.notebook.schema import Exhibit


def _get_weighted_aggregate_data_REFACTORED(self, exhibit: Exhibit) -> Any:
    """
    Get data for weighted aggregate charts using unified measure framework.

    This replaces the old approach of querying materialized views with on-demand
    measure calculation using the model's measure executor.

    Key changes from old version:
    1. Uses model.calculate_measure() instead of querying views
    2. Works with both DuckDB and Spark (backend abstraction)
    3. No dependency on build_weighted_aggregates_duckdb.py script
    4. Leverages all measure framework features (filters, normalization, etc.)
    5. Consistent with rest of framework

    Args:
        exhibit: Weighted aggregate chart exhibit configuration

    Returns:
        DuckDB relation with columns: aggregate_by, weighted_value, measure_id

    Raises:
        ValueError: If exhibit configuration is invalid or measures not found
    """
    # Validate exhibit configuration
    if not hasattr(exhibit, 'value_measures') or not exhibit.value_measures:
        raise ValueError(
            f"Weighted aggregate exhibit {exhibit.id} has no value_measures defined. "
            f"Expected format: value_measures: ['measure_name1', 'measure_name2']"
        )

    # Get grouping column (default: trade_date)
    aggregate_by = exhibit.aggregate_by or 'trade_date'

    # Get model from session
    # Parse model name from exhibit source (format: "model.table")
    model_name = 'company'  # Default
    if hasattr(exhibit, 'source') and exhibit.source:
        try:
            model_name = self._parse_source(exhibit.source)[0]
        except ValueError:
            # If source is not in "model.table" format, use default
            pass

    # Get model session
    model = self.get_model_session(model_name)
    if not model:
        available_models = list(self.model_sessions.keys())
        raise ValueError(
            f"Model '{model_name}' not available. "
            f"Available models: {available_models}. "
            f"Check that model is loaded in notebook configuration."
        )

    # Build filters from exhibit configuration and filter context
    filters = self._build_filters(exhibit)

    # Convert filters to measure framework format
    # The measure framework expects filters as Dict[str, Any]
    # Date ranges: {'column': {'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'}}
    # Lists: {'column': ['value1', 'value2']}
    # Single values: {'column': 'value'}

    # Note: Weighted aggregates don't have ticker column (already aggregated)
    # So we skip dimension filters that don't exist in aggregated results
    skip_filters = {'ticker', 'symbol', 'stock_id', 'holding_ticker'}
    measure_filters = {
        k: v for k, v in filters.items()
        if k not in skip_filters
    }

    # Calculate each measure using unified framework
    results = []
    for measure_name in exhibit.value_measures:
        try:
            # Call model.calculate_measure() - this is the KEY CHANGE!
            result = model.calculate_measure(
                measure_name,
                filters=measure_filters,
                # entity_column is optional - weighted measures typically aggregate across all entities
                # Additional kwargs can be passed from exhibit config if needed
            )

            # Get result data as pandas DataFrame
            measure_df = result.data.copy()

            # Rename measure_value column to match chart expectations
            # Weighted measures return 'weighted_value', simple measures return 'measure_value'
            if 'weighted_value' not in measure_df.columns and 'measure_value' in measure_df.columns:
                measure_df['weighted_value'] = measure_df['measure_value']
                measure_df = measure_df.drop(columns=['measure_value'])

            # Add measure_id column for chart rendering
            # This allows the chart to display multiple measures with different colors/legends
            measure_df['measure_id'] = measure_name

            # Apply normalization if configured in exhibit
            # Normalization sets the first value to 100 and scales everything relative to it
            # Useful for comparing multiple indices with different scales
            if hasattr(exhibit, 'normalize') and exhibit.normalize:
                if len(measure_df) > 0 and aggregate_by in measure_df.columns:
                    # Sort by grouping column to ensure correct base value
                    measure_df = measure_df.sort_values(aggregate_by)

                    # Get base value (first value in sorted data)
                    base_value = measure_df.iloc[0]['weighted_value']

                    if base_value and base_value != 0:
                        # Normalize: (value / base_value) * 100
                        measure_df['weighted_value'] = (measure_df['weighted_value'] / base_value) * 100

            results.append(measure_df)

        except ValueError as e:
            # Provide helpful error message
            raise ValueError(
                f"Error calculating measure '{measure_name}': {str(e)}\n\n"
                f"Troubleshooting steps:\n"
                f"  1. Check that '{measure_name}' is defined in configs/models/{model_name}.yaml\n"
                f"  2. Verify measure type is 'weighted' for weighted aggregate charts\n"
                f"  3. Use model.measures.list_measures() to see available measures\n"
                f"  4. Use model.measures.explain_measure('{measure_name}') to see generated SQL\n"
                f"\nSee docs/TESTING_GUIDE.md for more help."
            )

    # Combine all measures into a single DataFrame
    if results:
        combined_df = pd.concat(results, ignore_index=True)

        # Ensure required columns exist
        required_cols = [aggregate_by, 'weighted_value', 'measure_id']
        missing_cols = [col for col in required_cols if col not in combined_df.columns]
        if missing_cols:
            raise ValueError(
                f"Measure calculation did not return expected columns. "
                f"Missing: {missing_cols}, Got: {list(combined_df.columns)}"
            )

        # Convert to DuckDB relation for consistency with other exhibit types
        # This allows the same exhibit rendering code to work with both DuckDB and Spark
        return self.connection.conn.from_df(combined_df)
    else:
        # Return empty DataFrame with correct schema
        return self.connection.conn.from_df(
            pd.DataFrame(columns=[aggregate_by, 'weighted_value', 'measure_id'])
        )


# ============================================================================
# COMPARISON: OLD vs NEW Implementation
# ============================================================================

def _get_weighted_aggregate_data_OLD(self, exhibit: Exhibit) -> Any:
    """
    OLD IMPLEMENTATION - Queries materialized views.

    Issues with this approach:
    1. Requires running build_weighted_aggregates_duckdb.py script
    2. Only works with DuckDB (no Spark support)
    3. Manual SQL construction
    4. Normalization logic hardcoded
    5. Views need to be kept in sync with model changes
    """
    # ... filter building code ...

    # PROBLEM: Queries materialized views directly
    results = []
    for measure_id in exhibit.value_measures:
        sql = f"""
        WITH raw_data AS (
            SELECT
                trade_date,
                weighted_value
            FROM {measure_id}  -- <-- Direct view query! View must exist.
            WHERE {where_clause}
            ORDER BY trade_date
        ),
        base_value AS (
            SELECT weighted_value as base_weighted_value
            FROM raw_data
            LIMIT 1
        )
        SELECT
            rd.trade_date,
            (rd.weighted_value / bv.base_weighted_value) * 100 as weighted_value,
            '{measure_id}' as measure_id
        FROM raw_data rd
        CROSS JOIN base_value bv
        """

        # Execute raw SQL
        df = self.connection.conn.execute(sql).fetchdf()
        results.append(df)

    return self.connection.conn.from_df(pd.concat(results))


# ============================================================================
# MIGRATION CHECKLIST
# ============================================================================

"""
Step-by-step migration:

1. BACKUP CURRENT CODE
   - Copy app/notebook/api/notebook_session.py to notebook_session.py.backup
   - Create git branch: git checkout -b streamlit-measure-integration

2. UPDATE _get_weighted_aggregate_data() METHOD
   - Replace lines 345-448 in notebook_session.py
   - Use _get_weighted_aggregate_data_REFACTORED() code above

3. UPDATE IMPORTS (if needed)
   - Ensure pandas is imported: import pandas as pd
   - Ensure typing imports: from typing import Any, Dict

4. TEST WITH PIPELINE TESTER
   python tests/pipeline_tester.py --verbose

5. TEST WITH BASIC EXAMPLE
   python examples/measure_framework/01_basic_usage.py

6. TEST STREAMLIT APP
   streamlit run app/main.py
   - Navigate to page with weighted aggregate chart
   - Verify chart loads
   - Test filtering
   - Check console for errors

7. UPDATE __init__.py IMPORT
   File: app/ui/components/exhibits/__init__.py
   Change:
     from .weighted_aggregate_chart import render_weighted_aggregate_chart
   To:
     from .weighted_aggregate_chart_model import render_weighted_aggregate_chart

8. ARCHIVE OLD COMPONENT (optional)
   mv app/ui/components/exhibits/weighted_aggregate_chart.py \\
      docs/archive/experimental/weighted_aggregate_chart_legacy.py

9. UPDATE DOCUMENTATION
   - Remove references to build_weighted_aggregates_duckdb.py from setup docs
   - Update README

10. COMMIT CHANGES
    git add .
    git commit -m "refactor: Integrate Streamlit app with unified measure framework

    - Update NotebookSession._get_weighted_aggregate_data() to use model.calculate_measure()
    - Remove dependency on materialized views
    - Support both DuckDB and Spark backends
    - Archive legacy weighted_aggregate_chart.py component

    See docs/STREAMLIT_REFACTORING_PLAN.md for details"

11. CREATE PR AND DEPLOY
    git push -u origin streamlit-measure-integration
    # Create PR on GitHub
    # After approval, merge and deploy
"""


# ============================================================================
# TESTING EXAMPLE
# ============================================================================

def test_refactored_implementation():
    """
    Example test for refactored implementation.

    Add this to tests/integration/test_streamlit_integration.py
    """
    from app.notebook.api.notebook_session import NotebookSession
    from core.context import RepoContext
    from app.notebook.schema import Exhibit, ExhibitType

    # Initialize context
    ctx = RepoContext.from_repo_root(connection_type='duckdb')

    # Create notebook session
    session = NotebookSession(ctx.connection, ctx.storage, ctx.repo)

    # Load model
    from models.implemented.company.model import CompanyModel
    model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

    # Add model to session
    session.model_sessions['company'] = {
        'model': model,
        'config': {},
        'initialized': True
    }

    # Create mock exhibit
    exhibit = Exhibit(
        id='test_weighted',
        type=ExhibitType.WEIGHTED_AGGREGATE_CHART,
        title='Test Weighted Aggregates',
        source='company.fact_prices',
        value_measures=[
            'equal_weighted_index',
            'volume_weighted_index'
        ],
        aggregate_by='trade_date',
        normalize=True
    )

    # Get data using refactored method
    result = session._get_weighted_aggregate_data(exhibit)

    # Verify result
    pdf = result.df()  # DuckDB relation to pandas
    print(f"Rows: {len(pdf)}")
    print(f"Columns: {list(pdf.columns)}")
    print(f"Measures: {pdf['measure_id'].unique()}")
    print(f"\nSample data:")
    print(pdf.head(10))

    # Assertions
    assert len(pdf) > 0, "No data returned"
    assert 'trade_date' in pdf.columns, "Missing trade_date column"
    assert 'weighted_value' in pdf.columns, "Missing weighted_value column"
    assert 'measure_id' in pdf.columns, "Missing measure_id column"

    measures = pdf['measure_id'].unique()
    assert 'equal_weighted_index' in measures, "Missing equal_weighted_index"
    assert 'volume_weighted_index' in measures, "Missing volume_weighted_index"

    # Check normalization (first value should be ~100)
    for measure_id in measures:
        measure_data = pdf[pdf['measure_id'] == measure_id].sort_values('trade_date')
        first_value = measure_data.iloc[0]['weighted_value']
        assert abs(first_value - 100) < 0.1, f"Normalization failed for {measure_id}"

    print("\n✓ All tests passed!")


if __name__ == '__main__':
    # Run test
    test_refactored_implementation()
