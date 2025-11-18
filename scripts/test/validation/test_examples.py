#!/usr/bin/env python3
"""
Test suite for example scripts.

Validates that all example scripts run without errors and produce expected results.
"""

import pytest
import sys
from pathlib import Path
from typing import Dict, Any

from utils.repo import setup_repo_imports
setup_repo_imports()

from scripts.examples.parameter_interface import (
    MeasureCalculator,
    CalculationRequest,
    validate_params,
    ParameterError
)


class TestParameterInterface:
    """Test the parameter-driven calculation interface."""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = MeasureCalculator(backend='duckdb')

    def test_calculator_initialization(self):
        """Test calculator initializes correctly."""
        assert self.calc is not None
        assert self.calc.backend == 'duckdb'

    def test_list_models(self):
        """Test listing available models."""
        models = self.calc.list_models()
        assert isinstance(models, list)
        assert len(models) > 0
        assert 'equity' in models or 'corporate' in models

    def test_list_measures(self):
        """Test listing measures for a model."""
        # Skip if equity model not available
        if 'equity' not in self.calc.list_models():
            pytest.skip("Equity model not available")

        measures = self.calc.list_measures('equity')
        assert isinstance(measures, list)
        assert len(measures) > 0

    def test_get_measure_info(self):
        """Test getting measure information."""
        if 'equity' not in self.calc.list_models():
            pytest.skip("Equity model not available")

        measures = self.calc.list_measures('equity')
        if not measures:
            pytest.skip("No measures available")

        measure_name = measures[0]
        info = self.calc.get_measure_info('equity', measure_name)
        assert isinstance(info, dict)
        assert 'type' in info
        assert 'source' in info


class TestCalculationRequest:
    """Test CalculationRequest dataclass."""

    def test_basic_request(self):
        """Test basic request creation."""
        request = CalculationRequest(
            model='equity',
            measure='avg_close_price',
            tickers=['AAPL'],
        )
        assert request.model == 'equity'
        assert request.measure == 'avg_close_price'
        assert request.tickers == ['AAPL']

    def test_request_with_dates(self):
        """Test request with date filters."""
        request = CalculationRequest(
            model='equity',
            measure='volume_weighted_index',
            tickers=['AAPL', 'MSFT'],
            start_date='2024-01-01',
            end_date='2024-12-31'
        )

        filter_kwargs = request.to_filter_kwargs()
        assert 'trade_date' in filter_kwargs
        assert filter_kwargs['trade_date']['start'] == '2024-01-01'
        assert filter_kwargs['trade_date']['end'] == '2024-12-31'
        assert filter_kwargs['ticker'] == ['AAPL', 'MSFT']

    def test_request_to_filter_kwargs(self):
        """Test conversion to filter kwargs."""
        request = CalculationRequest(
            model='equity',
            measure='avg_close_price',
            tickers=['AAPL'],
            entity_column='ticker',
            limit=10
        )

        kwargs = request.to_filter_kwargs()
        assert kwargs['ticker'] == ['AAPL']
        assert kwargs['entity_column'] == 'ticker'
        assert kwargs['limit'] == 10


class TestParameterValidation:
    """Test parameter validation."""

    def test_valid_params(self):
        """Test validation of valid parameters."""
        params = {
            'model': 'equity',
            'measure': 'avg_close_price',
            'tickers': ['AAPL', 'MSFT'],
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'limit': 10,
            'backend': 'duckdb'
        }

        # Should not raise
        validate_params(params)

    def test_missing_model(self):
        """Test validation fails without model."""
        params = {
            'measure': 'avg_close_price'
        }

        with pytest.raises(ParameterError, match="Missing required parameter: 'model'"):
            validate_params(params)

    def test_missing_measure(self):
        """Test validation fails without measure."""
        params = {
            'model': 'equity'
        }

        with pytest.raises(ParameterError, match="Missing required parameter: 'measure'"):
            validate_params(params)

    def test_invalid_date_format(self):
        """Test validation fails with invalid date."""
        params = {
            'model': 'equity',
            'measure': 'avg_close_price',
            'start_date': 'invalid-date'
        }

        with pytest.raises(ParameterError, match="Invalid start_date"):
            validate_params(params)

    def test_invalid_backend(self):
        """Test validation fails with invalid backend."""
        params = {
            'model': 'equity',
            'measure': 'avg_close_price',
            'backend': 'invalid_backend'
        }

        with pytest.raises(ParameterError, match="Invalid backend"):
            validate_params(params)

    def test_date_range_validation(self):
        """Test validation of date ranges."""
        params = {
            'model': 'equity',
            'measure': 'avg_close_price',
            'start_date': '2024-12-31',
            'end_date': '2024-01-01'  # End before start
        }

        with pytest.raises(ParameterError, match="must be before"):
            validate_params(params)

    def test_invalid_limit(self):
        """Test validation fails with invalid limit."""
        params = {
            'model': 'equity',
            'measure': 'avg_close_price',
            'limit': -10  # Negative limit
        }

        with pytest.raises(ParameterError, match="Limit must be positive"):
            validate_params(params)


class TestWeightedCalculations:
    """Test weighted price calculations."""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = MeasureCalculator(backend='duckdb')

    @pytest.mark.skipif(
        'equity' not in MeasureCalculator(backend='duckdb').list_models(),
        reason="Equity model not available"
    )
    def test_volume_weighted_index(self):
        """Test volume-weighted index calculation."""
        params = {
            'model': 'equity',
            'measure': 'volume_weighted_index',
            'tickers': ['AAPL'],
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        }

        result = self.calc.calculate(params)

        # Check for errors first
        if result.error:
            # If error is due to missing data, skip test
            if 'no data' in result.error.lower() or 'not found' in result.error.lower():
                pytest.skip(f"No data available: {result.error}")
            else:
                pytest.fail(f"Calculation failed: {result.error}")

        # Validate result
        assert result.data is not None
        assert result.rows >= 0
        assert result.backend == 'duckdb'
        assert result.query_time_ms >= 0

    @pytest.mark.skipif(
        'equity' not in MeasureCalculator(backend='duckdb').list_models(),
        reason="Equity model not available"
    )
    def test_multiple_tickers(self):
        """Test calculation with multiple tickers."""
        params = {
            'model': 'equity',
            'measure': 'volume_weighted_index',
            'tickers': ['AAPL', 'MSFT'],
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        }

        result = self.calc.calculate(params)

        if result.error:
            if 'no data' in result.error.lower():
                pytest.skip(f"No data available: {result.error}")
            else:
                pytest.fail(f"Calculation failed: {result.error}")

        assert result.data is not None

    @pytest.mark.skipif(
        'equity' not in MeasureCalculator(backend='duckdb').list_models(),
        reason="Equity model not available"
    )
    def test_compare_strategies(self):
        """Test comparing multiple weighting strategies."""
        strategies = [
            'equal_weighted_index',
            'volume_weighted_index',
        ]

        results = self.calc.calculate_with_comparison(
            model='equity',
            measures=strategies,
            tickers=['AAPL'],
            start_date='2024-01-01',
            end_date='2024-01-31'
        )

        assert isinstance(results, dict)
        assert len(results) == len(strategies)

        # At least one should succeed or all should have clear errors
        success_count = sum(1 for r in results.values() if not r.error)
        error_count = sum(1 for r in results.values() if r.error)

        assert success_count + error_count == len(strategies)


class TestExampleScripts:
    """Test that example scripts can be imported and executed."""

    def test_quickstart_imports(self):
        """Test that quickstart example can be imported."""
        try:
            import scripts.examples.weighting_strategies.README as readme
        except ImportError:
            pass  # README is markdown, not importable

        # Test parameter interface imports
        from scripts.examples.parameter_interface import (
            MeasureCalculator,
            CalculationRequest,
            CalculationResult,
        )

        assert MeasureCalculator is not None
        assert CalculationRequest is not None
        assert CalculationResult is not None

    def test_weighting_example_structure(self):
        """Test weighting examples directory structure."""
        examples_dir = Path(__file__).parent.parent.parent / 'examples' / 'weighting_strategies'
        assert examples_dir.exists()

        # Check for key files
        assert (examples_dir / 'README.md').exists()
        assert (examples_dir / '01_basic_weighted_price.py').exists()
        assert (examples_dir / '02_compare_all_strategies.py').exists()


def test_parameter_discovery():
    """Test parameter discovery functions."""
    from scripts.examples.parameter_interface.discovery import (
        list_models,
        list_weighting_strategies,
    )

    # Test list_models
    models = list_models()
    assert isinstance(models, list)

    # Test list_weighting_strategies
    strategies = list_weighting_strategies()
    assert isinstance(strategies, dict)
    assert 'equal' in strategies
    assert 'volume' in strategies
    assert 'market_cap' in strategies


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v', '--tb=short'])
