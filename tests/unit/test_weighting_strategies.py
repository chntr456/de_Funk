"""
Unit tests for weighting strategies.

Tests all equity and ETF weighting strategies.
"""

import sys
from pathlib import Path

# Add repository root to Python path
REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from models.implemented.equity.domains.weighting import (
    WeightingStrategy,
    EqualWeightStrategy,
    VolumeWeightStrategy,
    MarketCapWeightStrategy,
    PriceWeightStrategy,
    VolumeDeviationWeightStrategy,
    VolatilityWeightStrategy,
    get_weighting_strategy
)
from models.implemented.etf.domains.weighting import HoldingsWeightStrategy


class TestEqualWeightStrategy:
    """Test equal weighting strategy."""

    def test_generate_sql(self, mock_model):
        """Test SQL generation for equal weighting."""
        from models.base.backend.duckdb_adapter import DuckDBAdapter

        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        strategy = EqualWeightStrategy()

        sql = strategy.generate_sql(
            adapter=adapter,
            table_name='fact_prices',
            value_column='close',
            group_by=['trade_date']
        )

        assert 'AVG(close)' in sql
        assert 'GROUP BY trade_date' in sql
        assert 'COUNT(*)' in sql
        assert 'WHERE close IS NOT NULL' in sql


class TestVolumeWeightStrategy:
    """Test volume weighting strategy."""

    def test_generate_sql(self, mock_model):
        """Test SQL generation for volume weighting."""
        from models.base.backend.duckdb_adapter import DuckDBAdapter

        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        strategy = VolumeWeightStrategy()

        sql = strategy.generate_sql(
            adapter=adapter,
            table_name='fact_prices',
            value_column='close',
            group_by=['trade_date']
        )

        assert 'SUM(close * volume)' in sql
        assert 'NULLIF(SUM(volume), 0)' in sql
        assert 'WHERE close IS NOT NULL' in sql
        assert 'volume > 0' in sql
        assert 'SUM(volume) as total_volume' in sql


class TestMarketCapWeightStrategy:
    """Test market cap weighting strategy."""

    def test_generate_sql(self, mock_model):
        """Test SQL generation for market cap weighting."""
        from models.base.backend.duckdb_adapter import DuckDBAdapter

        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        strategy = MarketCapWeightStrategy()

        sql = strategy.generate_sql(
            adapter=adapter,
            table_name='fact_prices',
            value_column='close',
            group_by=['trade_date']
        )

        assert 'SUM(close * close * volume)' in sql
        assert 'SUM(close * volume)' in sql
        assert 'WHERE close IS NOT NULL' in sql
        assert 'close > 0' in sql
        assert 'volume > 0' in sql


class TestPriceWeightStrategy:
    """Test price weighting strategy."""

    def test_generate_sql(self, mock_model):
        """Test SQL generation for price weighting."""
        from models.base.backend.duckdb_adapter import DuckDBAdapter

        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        strategy = PriceWeightStrategy()

        sql = strategy.generate_sql(
            adapter=adapter,
            table_name='fact_prices',
            value_column='close',
            group_by=['trade_date']
        )

        assert 'SUM(close * close)' in sql
        assert 'SUM(close)' in sql
        assert 'WHERE close IS NOT NULL' in sql
        assert 'close > 0' in sql


class TestVolumeDeviationWeightStrategy:
    """Test volume deviation weighting strategy."""

    def test_generate_sql(self, mock_model):
        """Test SQL generation for volume deviation weighting."""
        from models.base.backend.duckdb_adapter import DuckDBAdapter

        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        strategy = VolumeDeviationWeightStrategy()

        sql = strategy.generate_sql(
            adapter=adapter,
            table_name='fact_prices',
            value_column='close',
            group_by=['trade_date']
        )

        assert 'WITH avg_volumes AS' in sql
        assert 'AVG(volume)' in sql
        assert 'ABS(f.volume - av.avg_volume)' in sql
        assert 'JOIN avg_volumes' in sql


class TestVolatilityWeightStrategy:
    """Test volatility weighting strategy."""

    def test_generate_sql(self, mock_model):
        """Test SQL generation for volatility weighting."""
        from models.base.backend.duckdb_adapter import DuckDBAdapter

        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        strategy = VolatilityWeightStrategy()

        sql = strategy.generate_sql(
            adapter=adapter,
            table_name='fact_prices',
            value_column='close',
            group_by=['trade_date']
        )

        assert 'WITH daily_ranges AS' in sql
        assert '(high - low) as daily_range' in sql
        assert 'SUM(close / NULLIF(daily_range, 0))' in sql
        assert 'WHERE daily_range > 0.001' in sql


class TestHoldingsWeightStrategy:
    """Test ETF holdings weighting strategy."""

    def test_generate_sql(self, mock_model):
        """Test SQL generation for holdings-based weighting."""
        from models.base.backend.duckdb_adapter import DuckDBAdapter

        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        strategy = HoldingsWeightStrategy()

        sql = strategy.generate_sql(
            adapter=adapter,
            table_name='company.fact_prices',
            value_column='close',
            group_by=['trade_date', 'etf_ticker'],
            weight_column='dim_etf_holdings.weight_percent'
        )

        assert 'JOIN' in sql
        assert 'holding_ticker' in sql
        assert 'weight_percent / 100.0' in sql  # Percentage conversion
        assert 'SUM(h.weight_percent)' in sql

    def test_missing_weight_column(self, mock_model):
        """Test error handling for missing weight column."""
        from models.base.backend.duckdb_adapter import DuckDBAdapter

        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        strategy = HoldingsWeightStrategy()

        with pytest.raises(ValueError, match="requires explicit weight_column"):
            strategy.generate_sql(
                adapter=adapter,
                table_name='fact_prices',
                value_column='close',
                group_by=['trade_date']
            )


class TestWeightingStrategyRegistry:
    """Test weighting strategy registry."""

    def test_get_equal_weight_strategy(self):
        """Test getting equal weight strategy."""
        strategy = get_weighting_strategy('equal')
        assert isinstance(strategy, EqualWeightStrategy)

    def test_get_volume_weight_strategy(self):
        """Test getting volume weight strategy."""
        strategy = get_weighting_strategy('volume')
        assert isinstance(strategy, VolumeWeightStrategy)

    def test_get_market_cap_weight_strategy(self):
        """Test getting market cap weight strategy."""
        strategy = get_weighting_strategy('market_cap')
        assert isinstance(strategy, MarketCapWeightStrategy)

    def test_get_price_weight_strategy(self):
        """Test getting price weight strategy."""
        strategy = get_weighting_strategy('price')
        assert isinstance(strategy, PriceWeightStrategy)

    def test_get_unknown_strategy(self):
        """Test error handling for unknown strategy."""
        with pytest.raises(ValueError, match="Unknown weighting method"):
            get_weighting_strategy('nonexistent')


class TestWeightedMeasureIntegration:
    """Test weighted measure with strategies."""

    def test_weighted_measure_with_volume_strategy(self, mock_model):
        """Test weighted measure using volume strategy."""
        from models.measures.weighted import WeightedMeasure
        from models.base.backend.duckdb_adapter import DuckDBAdapter

        config = {
            'name': 'volume_weighted_index',
            'source': 'fact_prices.close',
            'weighting_method': 'volume',
            'group_by': ['trade_date']
        }

        measure = WeightedMeasure(config)
        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        sql = measure.to_sql(adapter)

        assert 'SUM(close * volume)' in sql
        assert 'NULLIF(SUM(volume), 0)' in sql

    def test_weighted_measure_with_equal_strategy(self, mock_model):
        """Test weighted measure using equal strategy."""
        from models.measures.weighted import WeightedMeasure
        from models.base.backend.duckdb_adapter import DuckDBAdapter

        config = {
            'name': 'equal_weighted_index',
            'source': 'fact_prices.close',
            'weighting_method': 'equal',
            'group_by': ['trade_date']
        }

        measure = WeightedMeasure(config)
        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        sql = measure.to_sql(adapter)

        assert 'AVG(close)' in sql
        assert 'GROUP BY trade_date' in sql


class TestWeightingWithFilters:
    """Test weighting strategies with additional filters."""

    def test_volume_weight_with_filters(self, mock_model):
        """Test volume weighting with filters."""
        from models.base.backend.duckdb_adapter import DuckDBAdapter

        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        strategy = VolumeWeightStrategy()

        sql = strategy.generate_sql(
            adapter=adapter,
            table_name='fact_prices',
            value_column='close',
            group_by=['trade_date'],
            filters=["ticker IN ('AAPL', 'MSFT')"]
        )

        assert "ticker IN ('AAPL', 'MSFT')" in sql
        assert 'WHERE close IS NOT NULL' in sql
        assert 'volume > 0' in sql
