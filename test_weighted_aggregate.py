"""
Test weighted aggregate calculations.

Tests the core functionality of the weighted aggregate chart calculations
to ensure different weighting methods produce correct results.
"""

import pandas as pd
import numpy as np
from app.ui.components.exhibits.weighted_aggregate_chart import (
    calculate_weighted_aggregate,
    _calculate_group_weighted_aggregate
)


def test_equal_weighting():
    """Test equal weighting (simple average)."""
    df = pd.DataFrame({
        'trade_date': ['2024-01-01', '2024-01-01', '2024-01-01'],
        'ticker': ['AAPL', 'GOOGL', 'MSFT'],
        'close': [150.0, 100.0, 200.0],
        'volume': [1000, 2000, 3000]
    })

    result = calculate_weighted_aggregate(df, 'close', 'equal')

    assert not result.empty
    assert 'weighted_close' in result.columns
    # Equal weighted average: (150 + 100 + 200) / 3 = 150
    assert np.isclose(result['weighted_close'].iloc[0], 150.0)
    print("✓ Equal weighting test passed")


def test_volume_weighting():
    """Test volume weighting."""
    df = pd.DataFrame({
        'trade_date': ['2024-01-01', '2024-01-01', '2024-01-01'],
        'ticker': ['AAPL', 'GOOGL', 'MSFT'],
        'close': [100.0, 200.0, 300.0],
        'volume': [1000, 2000, 3000]
    })

    result = calculate_weighted_aggregate(df, 'close', 'volume')

    assert not result.empty
    # Volume weighted: (100*1000 + 200*2000 + 300*3000) / (1000+2000+3000)
    # = (100000 + 400000 + 900000) / 6000 = 1400000 / 6000 = 233.33
    expected = (100*1000 + 200*2000 + 300*3000) / (1000+2000+3000)
    assert np.isclose(result['weighted_close'].iloc[0], expected, rtol=1e-5)
    print("✓ Volume weighting test passed")


def test_price_weighting():
    """Test price weighting."""
    df = pd.DataFrame({
        'trade_date': ['2024-01-01', '2024-01-01', '2024-01-01'],
        'ticker': ['AAPL', 'GOOGL', 'MSFT'],
        'close': [100.0, 200.0, 300.0],
        'volume': [1000, 2000, 3000]
    })

    result = calculate_weighted_aggregate(df, 'close', 'price')

    assert not result.empty
    # Price weighted: (100*100 + 200*200 + 300*300) / (100+200+300)
    # = (10000 + 40000 + 90000) / 600 = 140000 / 600 = 233.33
    expected = (100*100 + 200*200 + 300*300) / (100+200+300)
    assert np.isclose(result['weighted_close'].iloc[0], expected, rtol=1e-5)
    print("✓ Price weighting test passed")


def test_market_cap_weighting():
    """Test market cap weighting."""
    df = pd.DataFrame({
        'trade_date': ['2024-01-01', '2024-01-01', '2024-01-01'],
        'ticker': ['AAPL', 'GOOGL', 'MSFT'],
        'close': [100.0, 200.0, 300.0],
        'volume': [1000, 2000, 1000]
    })

    result = calculate_weighted_aggregate(df, 'close', 'market_cap')

    assert not result.empty
    # Market cap = price * volume
    # Weights: 100*1000=100k, 200*2000=400k, 300*1000=300k
    # Weighted avg: (100*100k + 200*400k + 300*300k) / (100k+400k+300k)
    # = (10M + 80M + 90M) / 800k = 180M / 800k = 225
    weights = np.array([100*1000, 200*2000, 300*1000])
    values = np.array([100, 200, 300])
    expected = np.sum(values * weights) / np.sum(weights)
    assert np.isclose(result['weighted_close'].iloc[0], expected, rtol=1e-5)
    print("✓ Market cap weighting test passed")


def test_multiple_dates():
    """Test aggregation across multiple dates."""
    df = pd.DataFrame({
        'trade_date': ['2024-01-01', '2024-01-01', '2024-01-02', '2024-01-02'],
        'ticker': ['AAPL', 'GOOGL', 'AAPL', 'GOOGL'],
        'close': [100.0, 200.0, 110.0, 210.0],
        'volume': [1000, 2000, 1100, 2100]
    })

    result = calculate_weighted_aggregate(df, 'close', 'equal')

    assert len(result) == 2  # Two dates
    assert 'trade_date' in result.columns
    # First date: (100 + 200) / 2 = 150
    assert np.isclose(result[result['trade_date'] == '2024-01-01']['weighted_close'].iloc[0], 150.0)
    # Second date: (110 + 210) / 2 = 160
    assert np.isclose(result[result['trade_date'] == '2024-01-02']['weighted_close'].iloc[0], 160.0)
    print("✓ Multiple dates test passed")


def test_normalization():
    """Test weight normalization."""
    group = pd.DataFrame({
        'close': [100.0, 200.0],
        'volume': [1000, 2000]
    })

    # Without normalization
    result_no_norm = _calculate_group_weighted_aggregate(group, 'close', 'volume', None, False)

    # With normalization
    result_norm = _calculate_group_weighted_aggregate(group, 'close', 'volume', None, True)

    # Both should give same result for weighted average
    # (100*1000 + 200*2000) / (1000+2000) = 166.67
    expected = (100*1000 + 200*2000) / (1000+2000)
    assert np.isclose(result_norm, expected, rtol=1e-5)
    print("✓ Normalization test passed")


def test_nan_handling():
    """Test handling of NaN values."""
    df = pd.DataFrame({
        'trade_date': ['2024-01-01', '2024-01-01', '2024-01-01'],
        'ticker': ['AAPL', 'GOOGL', 'MSFT'],
        'close': [100.0, np.nan, 200.0],
        'volume': [1000, 2000, 3000]
    })

    result = calculate_weighted_aggregate(df, 'close', 'equal')

    assert not result.empty
    # Should ignore NaN: (100 + 200) / 2 = 150
    assert np.isclose(result['weighted_close'].iloc[0], 150.0)
    print("✓ NaN handling test passed")


def test_volume_deviation_weighting():
    """Test volume deviation weighting."""
    df = pd.DataFrame({
        'trade_date': ['2024-01-01', '2024-01-01', '2024-01-01'],
        'ticker': ['AAPL', 'GOOGL', 'MSFT'],
        'close': [100.0, 200.0, 300.0],
        'volume': [1000, 3000, 2000]  # avg = 2000
    })

    result = calculate_weighted_aggregate(df, 'close', 'volume_deviation')

    assert not result.empty
    # Avg volume = 2000
    # Deviations: -1000, +1000, 0
    # Weights (abs): 1000*100=100k, 1000*200=200k, 0*300=0
    # Weighted avg: (100*100k + 200*200k + 300*0) / (100k+200k+0)
    # = (10M + 40M) / 300k = 50M / 300k = 166.67
    avg_volume = 2000
    deviations = np.abs(np.array([1000, 3000, 2000]) - avg_volume)
    prices = np.array([100.0, 200.0, 300.0])
    weights = deviations * prices
    values = np.array([100.0, 200.0, 300.0])
    expected = np.sum(values * weights) / np.sum(weights)
    assert np.isclose(result['weighted_close'].iloc[0], expected, rtol=1e-5)
    print("✓ Volume deviation weighting test passed")


def main():
    """Run all tests."""
    print("\n🧪 Running Weighted Aggregate Tests\n")
    print("=" * 50)

    tests = [
        test_equal_weighting,
        test_volume_weighting,
        test_price_weighting,
        test_market_cap_weighting,
        test_multiple_dates,
        test_normalization,
        test_nan_handling,
        test_volume_deviation_weighting,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1

    print("=" * 50)
    print(f"\n📊 Results: {passed} passed, {failed} failed\n")

    if failed == 0:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit(main())
