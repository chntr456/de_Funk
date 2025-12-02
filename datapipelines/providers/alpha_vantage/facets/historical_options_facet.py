"""
Historical Options Facet - Transform Alpha Vantage HISTORICAL_OPTIONS to normalized schema.

Handles options chain data including strike prices, expiration dates, Greeks, and implied volatility.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from datetime import datetime

from datapipelines.facets.base_facet import Facet

try:
    from pyspark.sql import DataFrame, functions as F
    HAS_SPARK = True
except ImportError:
    HAS_SPARK = False
    DataFrame = None


class HistoricalOptionsFacet(Facet):
    """
    Transform Alpha Vantage historical options data to normalized schema.

    API returns:
    {
        "data": [
            {
                "contractID": "AAPL230120C00150000",
                "symbol": "AAPL",
                "expiration": "2023-01-20",
                "strike": "150.00",
                "type": "call",
                "last": "5.25",
                "mark": "5.30",
                "bid": "5.20",
                "bid_size": "100",
                "ask": "5.40",
                "ask_size": "150",
                "volume": "1234",
                "open_interest": "5678",
                "date": "2023-01-15",
                "implied_volatility": "0.2345",
                "delta": "0.5123",
                "gamma": "0.0234",
                "theta": "-0.0156",
                "vega": "0.2345",
                "rho": "0.0567"
            },
            ...
        ]
    }
    """

    # Numeric fields that need type coercion
    NUMERIC_COERCE: Dict[str, str] = {
        "strike": "double",
        "last": "double",
        "mark": "double",
        "bid": "double",
        "ask": "double",
        "bid_size": "long",
        "ask_size": "long",
        "volume": "long",
        "open_interest": "long",
        "implied_volatility": "double",
        "delta": "double",
        "gamma": "double",
        "theta": "double",
        "vega": "double",
        "rho": "double",
    }

    # Final schema columns
    FINAL_COLUMNS: Optional[List[Tuple[str, str]]] = [
        ("contract_id", "string"),
        ("underlying_ticker", "string"),
        ("trade_date", "date"),
        ("expiration_date", "date"),
        ("strike_price", "double"),
        ("option_type", "string"),  # 'call' or 'put'
        # Prices
        ("last_price", "double"),
        ("mark_price", "double"),
        ("bid_price", "double"),
        ("ask_price", "double"),
        ("bid_size", "long"),
        ("ask_size", "long"),
        ("bid_ask_spread", "double"),
        # Volume
        ("volume", "long"),
        ("open_interest", "long"),
        # Greeks
        ("implied_volatility", "double"),
        ("delta", "double"),
        ("gamma", "double"),
        ("theta", "double"),
        ("vega", "double"),
        ("rho", "double"),
        # Derived
        ("days_to_expiration", "int"),
        ("moneyness", "double"),  # strike / underlying price
        ("in_the_money", "boolean"),
        # Metadata
        ("ingestion_timestamp", "timestamp"),
        ("snapshot_date", "date"),
    ]

    def __init__(self, spark, ticker: str = None, underlying_ticker: str = None,
                 underlying_price: float = None, **kwargs):
        """
        Initialize Historical Options Facet.

        Args:
            spark: Spark session
            ticker: Underlying ticker symbol (alias for underlying_ticker)
            underlying_ticker: Underlying ticker symbol
            underlying_price: Current underlying price (for moneyness calculation)
        """
        super().__init__(spark, **kwargs)
        self.ticker = underlying_ticker or ticker
        self.underlying_price = underlying_price

    def normalize(self, raw_response: dict) -> DataFrame:
        """
        Normalize historical options response.

        Args:
            raw_response: API response with 'data' array

        Returns:
            DataFrame with normalized options data
        """
        if not raw_response:
            return self._empty_df()

        # Handle both direct list and nested 'data' key
        if isinstance(raw_response, list):
            options_data = raw_response
        else:
            options_data = raw_response.get("data", [])

        if not options_data:
            return self._empty_df()

        all_options = []
        for option in options_data:
            all_options.append(self._transform_option(option))

        if not all_options:
            return self._empty_df()

        # Coerce numeric types
        all_options = self._coerce_rows(all_options)

        # Create DataFrame
        df = self.spark.createDataFrame(all_options, samplingRatio=1.0)
        df = self.postprocess(df)
        df = self._apply_final_casts(df)
        df = self._apply_final_columns(df)

        return df

    def _transform_option(self, option: dict) -> dict:
        """Transform a single option contract to normalized schema."""

        def safe_double(val):
            """Convert to double, handling None and 'None' strings."""
            if val is None or val == "None" or val == "":
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        def safe_long(val):
            """Convert to long, handling None and 'None' strings."""
            if val is None or val == "None" or val == "":
                return None
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return None

        now = datetime.now()

        strike = safe_double(option.get("strike"))
        bid = safe_double(option.get("bid"))
        ask = safe_double(option.get("ask"))
        option_type = option.get("type", "").lower()

        # Calculate bid-ask spread
        if bid is not None and ask is not None:
            bid_ask_spread = ask - bid
        else:
            bid_ask_spread = None

        # Calculate days to expiration
        expiration_str = option.get("expiration")
        trade_date_str = option.get("date")
        if expiration_str and trade_date_str:
            try:
                expiration = datetime.strptime(expiration_str, "%Y-%m-%d")
                trade_date = datetime.strptime(trade_date_str, "%Y-%m-%d")
                days_to_expiration = (expiration - trade_date).days
            except ValueError:
                days_to_expiration = None
        else:
            days_to_expiration = None

        # Calculate moneyness (strike / underlying)
        if strike is not None and self.underlying_price is not None and self.underlying_price > 0:
            moneyness = strike / self.underlying_price
            # Determine if in the money
            if option_type == "call":
                in_the_money = self.underlying_price > strike
            elif option_type == "put":
                in_the_money = self.underlying_price < strike
            else:
                in_the_money = None
        else:
            moneyness = None
            in_the_money = None

        return {
            "contract_id": option.get("contractID"),
            "underlying_ticker": option.get("symbol", self.ticker),
            "trade_date": trade_date_str,
            "expiration_date": expiration_str,
            "strike_price": strike,
            "option_type": option_type,
            # Prices
            "last_price": safe_double(option.get("last")),
            "mark_price": safe_double(option.get("mark")),
            "bid_price": bid,
            "ask_price": ask,
            "bid_size": safe_long(option.get("bid_size")),
            "ask_size": safe_long(option.get("ask_size")),
            "bid_ask_spread": bid_ask_spread,
            # Volume
            "volume": safe_long(option.get("volume")),
            "open_interest": safe_long(option.get("open_interest")),
            # Greeks
            "implied_volatility": safe_double(option.get("implied_volatility")),
            "delta": safe_double(option.get("delta")),
            "gamma": safe_double(option.get("gamma")),
            "theta": safe_double(option.get("theta")),
            "vega": safe_double(option.get("vega")),
            "rho": safe_double(option.get("rho")),
            # Derived
            "days_to_expiration": days_to_expiration,
            "moneyness": moneyness,
            "in_the_money": in_the_money,
            # Metadata
            "ingestion_timestamp": now,
            "snapshot_date": now.date(),
        }

    def postprocess(self, df: DataFrame) -> DataFrame:
        """Apply any post-processing transformations."""
        # Convert string dates to date type
        for date_col in ["trade_date", "expiration_date"]:
            if date_col in df.columns:
                df = df.withColumn(
                    date_col,
                    F.to_date(F.col(date_col), "yyyy-MM-dd")
                )
        return df
