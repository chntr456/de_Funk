"""
Corporate fundamental analysis patterns.

Provides reusable patterns for calculating financial ratios
and fundamental metrics from financial statement data.

These patterns will be fully functional once SEC EDGAR or
financial data provider integration is complete.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class FundamentalRatioStrategy(ABC):
    """Base class for fundamental ratio calculations."""

    @abstractmethod
    def generate_sql(self, adapter, **kwargs) -> str:
        """
        Generate SQL to calculate this ratio.

        Args:
            adapter: BackendAdapter (DuckDB or Spark)
            **kwargs: Parameters specific to the ratio

        Returns:
            SQL string
        """
        pass


class PERatioStrategy(FundamentalRatioStrategy):
    """
    Price to Earnings (P/E) ratio calculation.

    P/E Ratio = Stock Price / Earnings Per Share (EPS)

    Interpretation:
    - High P/E: Stock is expensive relative to earnings (growth expected)
    - Low P/E: Stock is cheap relative to earnings (value opportunity or problems)
    - P/E < 0: Company is not profitable
    """

    def generate_sql(
        self,
        adapter,
        financials_table: str,
        prices_table: str,
        **kwargs
    ) -> str:
        """
        Calculate P/E ratio by joining equity prices with financial statements.

        Requires:
        - Corporate financials (eps_diluted)
        - Equity prices (close price)
        - Cross-model join via company_id/ticker
        """
        financials_ref = adapter.get_table_reference(financials_table)
        prices_ref = adapter.get_table_reference(prices_table)

        return f"""
        SELECT
            f.company_id,
            e.ticker,
            f.report_date,
            p.close as stock_price,
            f.eps_diluted,
            CASE
                WHEN f.eps_diluted > 0 THEN p.close / f.eps_diluted
                WHEN f.eps_diluted < 0 THEN p.close / f.eps_diluted  -- Negative P/E
                ELSE NULL
            END as pe_ratio
        FROM {financials_ref} f
        INNER JOIN corporate.dim_corporate c ON f.company_id = c.company_id
        INNER JOIN equity.dim_equity e ON c.ticker_primary = e.ticker
        INNER JOIN {prices_ref} p ON e.ticker = p.ticker
        WHERE f.statement_type = 'income'
          AND f.report_period = 'FY'  -- Annual only
          AND f.eps_diluted IS NOT NULL
          -- Use price from shortly after report date
          AND p.trade_date >= f.report_date
          AND p.trade_date < f.report_date + INTERVAL '90 days'
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY f.company_id, f.report_date
            ORDER BY p.trade_date DESC
        ) = 1
        ORDER BY f.company_id, f.report_date
        """


class ROEStrategy(FundamentalRatioStrategy):
    """
    Return on Equity (ROE) calculation.

    ROE = Net Income / Shareholder's Equity * 100

    Interpretation:
    - High ROE: Company efficiently generates profit from equity
    - ROE > 15%: Generally considered good
    - ROE < 0: Company is losing money
    """

    def generate_sql(
        self,
        adapter,
        financials_table: str,
        **kwargs
    ) -> str:
        """
        Calculate ROE from financial statements.

        Requires income statement (net_income) and balance sheet (total_equity).
        """
        financials_ref = adapter.get_table_reference(financials_table)

        return f"""
        WITH income AS (
            SELECT
                company_id,
                report_date,
                fiscal_year,
                net_income
            FROM {financials_ref}
            WHERE statement_type = 'income'
              AND report_period = 'FY'
              AND net_income IS NOT NULL
        ),
        balance AS (
            SELECT
                company_id,
                report_date,
                fiscal_year,
                total_equity
            FROM {financials_ref}
            WHERE statement_type = 'balance_sheet'
              AND total_equity IS NOT NULL
              AND total_equity > 0
        )
        SELECT
            i.company_id,
            i.report_date,
            i.fiscal_year,
            i.net_income,
            b.total_equity,
            (i.net_income / b.total_equity) * 100 as roe_percent
        FROM income i
        INNER JOIN balance b
            ON i.company_id = b.company_id
            AND i.fiscal_year = b.fiscal_year
        ORDER BY i.company_id, i.report_date
        """


class DebtToEquityStrategy(FundamentalRatioStrategy):
    """
    Debt to Equity (D/E) ratio calculation.

    D/E = Total Liabilities / Total Equity

    Interpretation:
    - High D/E: Company is leveraged (risky but can amplify returns)
    - Low D/E: Company is conservative (safer but may miss opportunities)
    - D/E > 2: Generally considered high leverage
    - D/E < 0.5: Generally considered low leverage
    """

    def generate_sql(
        self,
        adapter,
        financials_table: str,
        **kwargs
    ) -> str:
        """
        Calculate D/E ratio from balance sheet.

        Requires total_liabilities and total_equity.
        """
        financials_ref = adapter.get_table_reference(financials_table)

        return f"""
        SELECT
            company_id,
            report_date,
            fiscal_year,
            report_period,
            total_liabilities,
            total_equity,
            CASE
                WHEN total_equity > 0 THEN total_liabilities / total_equity
                ELSE NULL
            END as debt_to_equity
        FROM {financials_ref}
        WHERE statement_type = 'balance_sheet'
          AND total_liabilities IS NOT NULL
          AND total_equity IS NOT NULL
          AND total_equity > 0
        ORDER BY company_id, report_date
        """


class ProfitMarginStrategy(FundamentalRatioStrategy):
    """
    Profit margin calculations (gross, operating, net).

    - Gross Margin = (Revenue - Cost of Revenue) / Revenue * 100
    - Operating Margin = Operating Income / Revenue * 100
    - Net Margin = Net Income / Revenue * 100
    """

    def __init__(self, margin_type: str = 'net'):
        """
        Args:
            margin_type: Type of margin ('gross', 'operating', 'net')
        """
        self.margin_type = margin_type.lower()

    def generate_sql(
        self,
        adapter,
        financials_table: str,
        **kwargs
    ) -> str:
        """Calculate profit margins from income statement."""
        financials_ref = adapter.get_table_reference(financials_table)

        if self.margin_type == 'gross':
            numerator = "gross_profit"
        elif self.margin_type == 'operating':
            numerator = "operating_income"
        elif self.margin_type == 'net':
            numerator = "net_income"
        else:
            raise ValueError(f"Invalid margin_type: {self.margin_type}")

        return f"""
        SELECT
            company_id,
            report_date,
            fiscal_year,
            report_period,
            revenue,
            {numerator},
            CASE
                WHEN revenue > 0 THEN ({numerator} / revenue) * 100
                ELSE NULL
            END as {self.margin_type}_margin_percent
        FROM {financials_ref}
        WHERE statement_type = 'income'
          AND revenue IS NOT NULL
          AND revenue > 0
          AND {numerator} IS NOT NULL
        ORDER BY company_id, report_date
        """


class CurrentRatioStrategy(FundamentalRatioStrategy):
    """
    Current Ratio calculation (liquidity measure).

    Current Ratio = Current Assets / Current Liabilities

    Interpretation:
    - Ratio > 1: Company can pay short-term obligations
    - Ratio < 1: Company may have liquidity issues
    - Ratio > 2: Generally considered healthy
    """

    def generate_sql(
        self,
        adapter,
        financials_table: str,
        **kwargs
    ) -> str:
        """Calculate current ratio from balance sheet."""
        financials_ref = adapter.get_table_reference(financials_table)

        return f"""
        SELECT
            company_id,
            report_date,
            fiscal_year,
            report_period,
            current_assets,
            current_liabilities,
            CASE
                WHEN current_liabilities > 0 THEN current_assets / current_liabilities
                ELSE NULL
            END as current_ratio
        FROM {financials_ref}
        WHERE statement_type = 'balance_sheet'
          AND current_assets IS NOT NULL
          AND current_liabilities IS NOT NULL
          AND current_liabilities > 0
        ORDER BY company_id, report_date
        """


class GrowthRateStrategy(FundamentalRatioStrategy):
    """
    Year-over-Year growth rate calculation.

    Growth Rate = (Current - Prior) / Prior * 100

    Can be applied to revenue, earnings, etc.
    """

    def __init__(self, metric: str = 'revenue'):
        """
        Args:
            metric: Metric to calculate growth for ('revenue', 'net_income', 'eps_diluted')
        """
        self.metric = metric

    def generate_sql(
        self,
        adapter,
        financials_table: str,
        **kwargs
    ) -> str:
        """Calculate YoY growth rate."""
        financials_ref = adapter.get_table_reference(financials_table)

        return f"""
        WITH yearly_data AS (
            SELECT
                company_id,
                fiscal_year,
                {self.metric}
            FROM {financials_ref}
            WHERE statement_type = 'income'
              AND report_period = 'FY'
              AND {self.metric} IS NOT NULL
        ),
        with_prior AS (
            SELECT
                company_id,
                fiscal_year,
                {self.metric} as current_value,
                LAG({self.metric}) OVER (
                    PARTITION BY company_id
                    ORDER BY fiscal_year
                ) as prior_value
            FROM yearly_data
        )
        SELECT
            company_id,
            fiscal_year,
            current_value,
            prior_value,
            CASE
                WHEN prior_value > 0 THEN ((current_value - prior_value) / prior_value) * 100
                ELSE NULL
            END as {self.metric}_growth_yoy_percent
        FROM with_prior
        WHERE prior_value IS NOT NULL
        ORDER BY company_id, fiscal_year
        """


# Registry
_RATIO_REGISTRY = {
    'pe_ratio': PERatioStrategy,
    'roe': ROEStrategy,
    'debt_to_equity': DebtToEquityStrategy,
    'profit_margin': ProfitMarginStrategy,
    'current_ratio': CurrentRatioStrategy,
    'growth_rate': GrowthRateStrategy,
}


def get_fundamental_ratio_strategy(ratio_type: str, **kwargs) -> FundamentalRatioStrategy:
    """
    Factory function to get fundamental ratio strategy.

    Args:
        ratio_type: Type of ratio ('pe_ratio', 'roe', 'debt_to_equity', etc.)
        **kwargs: Parameters for the strategy

    Returns:
        FundamentalRatioStrategy instance

    Example:
        # Get P/E ratio strategy
        strategy = get_fundamental_ratio_strategy('pe_ratio')

        # Get ROE strategy
        strategy = get_fundamental_ratio_strategy('roe')

        # Get profit margin strategy (specific type)
        strategy = get_fundamental_ratio_strategy('profit_margin', margin_type='gross')

        # Get growth rate strategy (specific metric)
        strategy = get_fundamental_ratio_strategy('growth_rate', metric='net_income')
    """
    strategy_class = _RATIO_REGISTRY.get(ratio_type.lower())
    if not strategy_class:
        raise ValueError(
            f"Unknown fundamental ratio: {ratio_type}. "
            f"Available: {list(_RATIO_REGISTRY.keys())}"
        )

    return strategy_class(**kwargs)


__all__ = [
    'FundamentalRatioStrategy',
    'PERatioStrategy',
    'ROEStrategy',
    'DebtToEquityStrategy',
    'ProfitMarginStrategy',
    'CurrentRatioStrategy',
    'GrowthRateStrategy',
    'get_fundamental_ratio_strategy',
]
