"""
State Builder - Generate US state dimension data.

Builds dim_state with:
- 50 US states
- District of Columbia
- US territories (Puerto Rico, Guam, Virgin Islands, etc.)

Data sources:
- FIPS codes from Census Bureau
- Census regions and divisions
- Population from 2020 Census
- Land area from Census Geography
"""
from __future__ import annotations

from typing import List, Dict, Any
import pandas as pd

# US States and Territories data
# Source: US Census Bureau FIPS codes, 2020 Census population, Census regions
US_STATES_DATA = [
    # state_fips, state_code, state_name, region, division, is_state, population, land_area_sq_mi
    ("01", "AL", "Alabama", "South", "East South Central", True, 5024279, 50645.33),
    ("02", "AK", "Alaska", "West", "Pacific", True, 733391, 570640.95),
    ("04", "AZ", "Arizona", "West", "Mountain", True, 7151502, 113594.08),
    ("05", "AR", "Arkansas", "South", "West South Central", True, 3011524, 52035.48),
    ("06", "CA", "California", "West", "Pacific", True, 39538223, 155779.22),
    ("08", "CO", "Colorado", "West", "Mountain", True, 5773714, 103641.89),
    ("09", "CT", "Connecticut", "Northeast", "New England", True, 3605944, 4842.36),
    ("10", "DE", "Delaware", "South", "South Atlantic", True, 989948, 1948.54),
    ("11", "DC", "District of Columbia", "South", "South Atlantic", False, 689545, 61.05),
    ("12", "FL", "Florida", "South", "South Atlantic", True, 21538187, 53624.76),
    ("13", "GA", "Georgia", "South", "South Atlantic", True, 10711908, 57513.49),
    ("15", "HI", "Hawaii", "West", "Pacific", True, 1455271, 6422.63),
    ("16", "ID", "Idaho", "West", "Mountain", True, 1839106, 82643.12),
    ("17", "IL", "Illinois", "Midwest", "East North Central", True, 12812508, 55518.93),
    ("18", "IN", "Indiana", "Midwest", "East North Central", True, 6785528, 35826.11),
    ("19", "IA", "Iowa", "Midwest", "West North Central", True, 3190369, 55857.13),
    ("20", "KS", "Kansas", "Midwest", "West North Central", True, 2937880, 81758.72),
    ("21", "KY", "Kentucky", "South", "East South Central", True, 4505836, 39486.34),
    ("22", "LA", "Louisiana", "South", "West South Central", True, 4657757, 43203.90),
    ("23", "ME", "Maine", "Northeast", "New England", True, 1362359, 30842.92),
    ("24", "MD", "Maryland", "South", "South Atlantic", True, 6177224, 9707.24),
    ("25", "MA", "Massachusetts", "Northeast", "New England", True, 7029917, 7800.06),
    ("26", "MI", "Michigan", "Midwest", "East North Central", True, 10077331, 56538.90),
    ("27", "MN", "Minnesota", "Midwest", "West North Central", True, 5706494, 79626.74),
    ("28", "MS", "Mississippi", "South", "East South Central", True, 2961279, 46923.27),
    ("29", "MO", "Missouri", "Midwest", "West North Central", True, 6154913, 68741.52),
    ("30", "MT", "Montana", "West", "Mountain", True, 1084225, 145545.80),
    ("31", "NE", "Nebraska", "Midwest", "West North Central", True, 1961504, 76824.17),
    ("32", "NV", "Nevada", "West", "Mountain", True, 3104614, 109781.18),
    ("33", "NH", "New Hampshire", "Northeast", "New England", True, 1377529, 8952.65),
    ("34", "NJ", "New Jersey", "Northeast", "Middle Atlantic", True, 9288994, 7354.22),
    ("35", "NM", "New Mexico", "West", "Mountain", True, 2117522, 121298.15),
    ("36", "NY", "New York", "Northeast", "Middle Atlantic", True, 20201249, 47126.40),
    ("37", "NC", "North Carolina", "South", "South Atlantic", True, 10439388, 48617.91),
    ("38", "ND", "North Dakota", "Midwest", "West North Central", True, 779094, 69000.80),
    ("39", "OH", "Ohio", "Midwest", "East North Central", True, 11799448, 40860.69),
    ("40", "OK", "Oklahoma", "South", "West South Central", True, 3959353, 68594.92),
    ("41", "OR", "Oregon", "West", "Pacific", True, 4237256, 95988.01),
    ("42", "PA", "Pennsylvania", "Northeast", "Middle Atlantic", True, 13002700, 44742.70),
    ("44", "RI", "Rhode Island", "Northeast", "New England", True, 1097379, 1033.81),
    ("45", "SC", "South Carolina", "South", "South Atlantic", True, 5118425, 30060.70),
    ("46", "SD", "South Dakota", "Midwest", "West North Central", True, 886667, 75811.00),
    ("47", "TN", "Tennessee", "South", "East South Central", True, 6910840, 41234.90),
    ("48", "TX", "Texas", "South", "West South Central", True, 29145505, 261231.71),
    ("49", "UT", "Utah", "West", "Mountain", True, 3271616, 82169.62),
    ("50", "VT", "Vermont", "Northeast", "New England", True, 643077, 9216.66),
    ("51", "VA", "Virginia", "South", "South Atlantic", True, 8631393, 39490.09),
    ("53", "WA", "Washington", "West", "Pacific", True, 7705281, 66455.52),
    ("54", "WV", "West Virginia", "South", "South Atlantic", True, 1793716, 24038.21),
    ("55", "WI", "Wisconsin", "Midwest", "East North Central", True, 5893718, 54157.80),
    ("56", "WY", "Wyoming", "West", "Mountain", True, 576851, 97093.14),
    # US Territories
    ("60", "AS", "American Samoa", "Pacific", "Pacific", False, 55191, 76.83),
    ("66", "GU", "Guam", "Pacific", "Pacific", False, 159358, 210.01),
    ("69", "MP", "Northern Mariana Islands", "Pacific", "Pacific", False, 47329, 182.12),
    ("72", "PR", "Puerto Rico", "Caribbean", "Caribbean", False, 3285874, 3423.78),
    ("78", "VI", "U.S. Virgin Islands", "Caribbean", "Caribbean", False, 87146, 133.73),
]


class StateBuilder:
    """
    Builder for US state dimension data.

    Generates dim_state with all 50 US states, DC, and territories
    with Census Bureau FIPS codes, regions, divisions, and demographics.

    Usage:
        builder = StateBuilder()
        df = builder.build_pandas_dataframe()
        spark_df = builder.build_spark_dataframe(spark)
    """

    def __init__(self, include_territories: bool = True):
        """
        Initialize StateBuilder.

        Args:
            include_territories: Include US territories (PR, GU, etc.)
        """
        self.include_territories = include_territories

    def build_pandas_dataframe(self) -> pd.DataFrame:
        """
        Build state dimension as pandas DataFrame.

        Returns:
            DataFrame with state dimension data
        """
        records = []

        for row in US_STATES_DATA:
            state_fips, state_code, state_name, region, division, is_state, population, land_area = row

            # Skip territories if not included
            if not is_state and not self.include_territories:
                continue

            records.append({
                'state_fips': state_fips,
                'state_code': state_code,
                'state_name': state_name,
                'region': region,
                'division': division,
                'is_state': is_state,
                'population': population,
                'land_area_sq_mi': land_area,
            })

        return pd.DataFrame(records)

    def build_spark_dataframe(self, spark) -> Any:
        """
        Build state dimension as Spark DataFrame.

        Args:
            spark: SparkSession

        Returns:
            Spark DataFrame with state dimension data
        """
        from pyspark.sql.types import (
            StructType, StructField, StringType, BooleanType,
            LongType, DoubleType
        )

        # Define schema
        schema = StructType([
            StructField("state_fips", StringType(), False),
            StructField("state_code", StringType(), False),
            StructField("state_name", StringType(), False),
            StructField("region", StringType(), True),
            StructField("division", StringType(), True),
            StructField("is_state", BooleanType(), False),
            StructField("population", LongType(), True),
            StructField("land_area_sq_mi", DoubleType(), True),
        ])

        # Build pandas first, then convert
        pdf = self.build_pandas_dataframe()

        return spark.createDataFrame(pdf, schema=schema)

    def get_regions(self) -> List[str]:
        """Get list of Census regions."""
        return ["Northeast", "South", "Midwest", "West", "Pacific", "Caribbean"]

    def get_divisions(self) -> List[str]:
        """Get list of Census divisions."""
        return [
            "New England", "Middle Atlantic",  # Northeast
            "South Atlantic", "East South Central", "West South Central",  # South
            "East North Central", "West North Central",  # Midwest
            "Mountain", "Pacific",  # West
            "Caribbean"  # Territories
        ]
