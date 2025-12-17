"""
ActuarialModel - Mortality, demographics, and risk analysis.

Inherits all graph building logic from BaseModel.
Provides actuarial-specific calculations and convenience methods.

Version: 2.0 - Backend-agnostic via UniversalSession methods
"""
from __future__ import annotations

from typing import Optional, Any, Dict, List
from models.base.model import BaseModel
import logging

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any


class ActuarialModel(BaseModel):
    """
    Actuarial model for mortality and demographic analysis.

    Inherits all functionality from BaseModel:
    - Generic graph building from YAML config
    - Node loading from Bronze
    - Table access methods

    Key features:
    - Mortality table access and calculations
    - Demographic data by geography
    - Insurance experience analysis
    - Present value and valuation calculations

    Cross-model dependencies:
    - temporal: Time dimension for trend analysis
    - geography: Location dimension for geographic segmentation

    Backend-agnostic: uses session methods for all DataFrame operations.
    """

    # ============================================================
    # MORTALITY TABLE METHODS
    # ============================================================

    def get_mortality_tables(
        self,
        table_type: Optional[str] = None,
        gender: Optional[str] = None,
        smoker_status: Optional[str] = None
    ) -> DataFrame:
        """
        Get mortality table metadata.

        Args:
            table_type: Filter by table type (CSO, VBT, GAM, etc.)
            gender: Filter by gender (Male, Female, Unisex)
            smoker_status: Filter by smoker status

        Returns:
            DataFrame with mortality table metadata
        """
        df = self.get_dimension_df('dim_mortality_table')

        if self.session:
            if table_type:
                df = self.session.filter_by_value(df, 'table_type', table_type)
            if gender:
                df = self.session.filter_by_value(df, 'gender', gender)
            if smoker_status:
                df = self.session.filter_by_value(df, 'smoker_status', smoker_status)
            return self.session.order_by(df, ['table_year', 'table_name'])
        elif self.backend == 'spark':
            if table_type:
                df = df.filter(df.table_type == table_type)
            if gender:
                df = df.filter(df.gender == gender)
            if smoker_status:
                df = df.filter(df.smoker_status == smoker_status)
            return df.orderBy('table_year', 'table_name')
        else:
            if table_type:
                df = df[df['table_type'] == table_type]
            if gender:
                df = df[df['gender'] == gender]
            if smoker_status:
                df = df[df['smoker_status'] == smoker_status]
            return df.sort_values(['table_year', 'table_name']) if hasattr(df, 'sort_values') else df

    def get_mortality_rates(
        self,
        table_id: str,
        age_from: Optional[int] = None,
        age_to: Optional[int] = None
    ) -> DataFrame:
        """
        Get mortality rates for a specific table.

        Args:
            table_id: Mortality table identifier
            age_from: Minimum age filter
            age_to: Maximum age filter

        Returns:
            DataFrame with mortality rates (qx, lx, dx, ex)
        """
        df = self.get_fact_df('fact_mortality_rates')

        if self.session:
            df = self.session.filter_by_value(df, 'table_id', table_id)
            if age_from is not None:
                df = self.session.filter_by_range(df, 'age', min_val=age_from)
            if age_to is not None:
                df = self.session.filter_by_range(df, 'age', max_val=age_to)
            return self.session.order_by(df, 'age')
        elif self.backend == 'spark':
            df = df.filter(df.table_id == table_id)
            if age_from is not None:
                df = df.filter(df.age >= age_from)
            if age_to is not None:
                df = df.filter(df.age <= age_to)
            return df.orderBy('age')
        else:
            df = df[df['table_id'] == table_id]
            if age_from is not None:
                df = df[df['age'] >= age_from]
            if age_to is not None:
                df = df[df['age'] <= age_to]
            return df.sort_values('age') if hasattr(df, 'sort_values') else df

    def get_qx(self, table_id: str, age: int) -> Optional[float]:
        """
        Get mortality rate (qx) for specific age.

        Args:
            table_id: Mortality table identifier
            age: Attained age

        Returns:
            Probability of death (qx) or None if not found
        """
        df = self.get_mortality_rates(table_id, age_from=age, age_to=age)

        if self.session:
            pdf = self.session.to_pandas(df)
        elif self.backend == 'spark':
            pdf = df.toPandas()
        else:
            pdf = df if hasattr(df, 'iloc') else df.df()

        if len(pdf) > 0:
            return float(pdf.iloc[0]['qx'])
        return None

    def get_life_expectancy(self, table_id: str, age: int) -> Optional[float]:
        """
        Get life expectancy at a specific age.

        Args:
            table_id: Mortality table identifier
            age: Attained age

        Returns:
            Life expectancy (ex) or None if not found
        """
        df = self.get_mortality_rates(table_id, age_from=age, age_to=age)

        if self.session:
            pdf = self.session.to_pandas(df)
        elif self.backend == 'spark':
            pdf = df.toPandas()
        else:
            pdf = df if hasattr(df, 'iloc') else df.df()

        if len(pdf) > 0:
            return float(pdf.iloc[0]['ex'])
        return None

    # ============================================================
    # DEMOGRAPHIC METHODS
    # ============================================================

    def get_demographics(
        self,
        state_fips: Optional[str] = None,
        year: Optional[int] = None,
        age_band_id: Optional[str] = None
    ) -> DataFrame:
        """
        Get demographic statistics.

        Args:
            state_fips: Filter by state FIPS code
            year: Filter by year
            age_band_id: Filter by age band

        Returns:
            DataFrame with demographic data
        """
        df = self.get_fact_df('fact_demographic_rates')

        if self.session:
            if state_fips:
                df = self.session.filter_by_value(df, 'state_fips', state_fips)
            if year:
                df = self.session.filter_by_value(df, 'year', year)
            if age_band_id:
                df = self.session.filter_by_value(df, 'age_band_id', age_band_id)
            return self.session.order_by(df, ['year', 'state_fips'])
        elif self.backend == 'spark':
            if state_fips:
                df = df.filter(df.state_fips == state_fips)
            if year:
                df = df.filter(df.year == year)
            if age_band_id:
                df = df.filter(df.age_band_id == age_band_id)
            return df.orderBy('year', 'state_fips')
        else:
            if state_fips:
                df = df[df['state_fips'] == state_fips]
            if year:
                df = df[df['year'] == year]
            if age_band_id:
                df = df[df['age_band_id'] == age_band_id]
            return df.sort_values(['year', 'state_fips']) if hasattr(df, 'sort_values') else df

    def get_demographics_with_geography(
        self,
        year: Optional[int] = None
    ) -> DataFrame:
        """
        Get demographics with full state geography context.

        Uses cross-model join to geography.dim_state.

        Args:
            year: Filter by year

        Returns:
            DataFrame with demographics and state details
        """
        if not self.session:
            raise RuntimeError(
                "ActuarialModel requires session for cross-model access. "
                "Call set_session() first."
            )

        demographics = self.get_demographics(year=year)

        # Cross-model join to geography
        geography_model = self.session.load_model('geography')
        states = geography_model.get_dimension_df('dim_state')

        return self.session.join(
            demographics,
            states,
            on=['state_fips'],
            how='left'
        )

    # ============================================================
    # EXPERIENCE STUDY METHODS
    # ============================================================

    def get_policy_experience(
        self,
        risk_class_id: Optional[str] = None,
        age_band_id: Optional[str] = None,
        state_fips: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> DataFrame:
        """
        Get insurance policy experience data.

        Args:
            risk_class_id: Filter by risk class
            age_band_id: Filter by age band
            state_fips: Filter by state
            date_from: Start date filter
            date_to: End date filter

        Returns:
            DataFrame with experience data
        """
        df = self.get_fact_df('fact_policy_experience')

        if self.session:
            if risk_class_id:
                df = self.session.filter_by_value(df, 'risk_class_id', risk_class_id)
            if age_band_id:
                df = self.session.filter_by_value(df, 'age_band_id', age_band_id)
            if state_fips:
                df = self.session.filter_by_value(df, 'state_fips', state_fips)
            df = self.session.filter_by_range(
                df, 'observation_date', min_val=date_from, max_val=date_to
            )
            return self.session.order_by(df, 'observation_date')
        elif self.backend == 'spark':
            if risk_class_id:
                df = df.filter(df.risk_class_id == risk_class_id)
            if age_band_id:
                df = df.filter(df.age_band_id == age_band_id)
            if state_fips:
                df = df.filter(df.state_fips == state_fips)
            if date_from:
                df = df.filter(df.observation_date >= date_from)
            if date_to:
                df = df.filter(df.observation_date <= date_to)
            return df.orderBy('observation_date')
        else:
            if risk_class_id:
                df = df[df['risk_class_id'] == risk_class_id]
            if age_band_id:
                df = df[df['age_band_id'] == age_band_id]
            if state_fips:
                df = df[df['state_fips'] == state_fips]
            if date_from:
                df = df[df['observation_date'] >= date_from]
            if date_to:
                df = df[df['observation_date'] <= date_to]
            return df.sort_values('observation_date') if hasattr(df, 'sort_values') else df

    def get_actual_to_expected(
        self,
        group_by: Optional[List[str]] = None
    ) -> DataFrame:
        """
        Calculate actual-to-expected ratios.

        Args:
            group_by: Columns to group by (e.g., ['risk_class_id', 'age_band_id'])

        Returns:
            DataFrame with A/E ratios by group
        """
        experience = self.get_policy_experience()

        if self.session:
            pdf = self.session.to_pandas(experience)
        elif self.backend == 'spark':
            pdf = experience.toPandas()
        else:
            pdf = experience if hasattr(experience, 'groupby') else experience.df()

        if group_by:
            result = pdf.groupby(group_by).agg(
                total_exposure=('exposure_count', 'sum'),
                total_claims=('claim_count', 'sum'),
                weighted_ae=('actual_to_expected', lambda x: (x * pdf.loc[x.index, 'exposure_count']).sum() / pdf.loc[x.index, 'exposure_count'].sum())
            ).reset_index()
        else:
            result = pdf.agg(
                total_exposure=('exposure_count', 'sum'),
                total_claims=('claim_count', 'sum'),
                avg_ae=('actual_to_expected', 'mean')
            )

        return result

    # ============================================================
    # ACTUARIAL CALCULATIONS
    # ============================================================

    def calculate_present_value_annuity(
        self,
        table_id: str,
        age: int,
        interest_rate: float = 0.045,
        years: Optional[int] = None
    ) -> float:
        """
        Calculate present value of a life annuity.

        Args:
            table_id: Mortality table identifier
            age: Starting age
            interest_rate: Annual interest rate
            years: Number of years (None for whole life)

        Returns:
            Present value of $1 annual annuity
        """
        rates = self.get_mortality_rates(table_id, age_from=age)

        if self.session:
            pdf = self.session.to_pandas(rates)
        elif self.backend == 'spark':
            pdf = rates.toPandas()
        else:
            pdf = rates if hasattr(rates, 'iloc') else rates.df()

        if len(pdf) == 0:
            return 0.0

        # Calculate present value using mortality rates
        v = 1 / (1 + interest_rate)  # Discount factor
        pv = 0.0
        tp = 1.0  # t-year survival probability

        max_years = years if years else len(pdf)

        for i, row in pdf.iterrows():
            if i - pdf.index[0] >= max_years:
                break

            qx = row['qx']
            px = 1 - qx  # Survival probability

            t = i - pdf.index[0] + 1
            pv += tp * (v ** t)
            tp *= px

        return pv

    def calculate_net_single_premium(
        self,
        table_id: str,
        age: int,
        face_amount: float = 1.0,
        interest_rate: float = 0.045
    ) -> float:
        """
        Calculate net single premium for whole life insurance.

        Args:
            table_id: Mortality table identifier
            age: Issue age
            face_amount: Face amount of insurance
            interest_rate: Annual interest rate

        Returns:
            Net single premium
        """
        rates = self.get_mortality_rates(table_id, age_from=age)

        if self.session:
            pdf = self.session.to_pandas(rates)
        elif self.backend == 'spark':
            pdf = rates.toPandas()
        else:
            pdf = rates if hasattr(rates, 'iloc') else rates.df()

        if len(pdf) == 0:
            return 0.0

        v = 1 / (1 + interest_rate)
        nsp = 0.0
        tp = 1.0  # t-year survival probability

        for i, row in pdf.iterrows():
            qx = row['qx']

            t = i - pdf.index[0] + 1
            nsp += tp * qx * (v ** t)
            tp *= (1 - qx)

        return nsp * face_amount

    # ============================================================
    # DIMENSION ACCESS
    # ============================================================

    def get_age_bands(self) -> DataFrame:
        """Get all age band definitions."""
        return self.get_dimension_df('dim_age_band')

    def get_risk_classes(self) -> DataFrame:
        """Get all risk class definitions."""
        return self.get_dimension_df('dim_risk_class')

    def list_mortality_tables(self) -> List[str]:
        """Get list of available mortality table IDs."""
        df = self.get_dimension_df('dim_mortality_table')

        if self.session:
            return self.session.distinct_values(df, 'table_id')
        elif self.backend == 'spark':
            return [row.table_id for row in df.select('table_id').distinct().collect()]
        else:
            if hasattr(df, 'df'):
                return df.df()['table_id'].unique().tolist()
            return df['table_id'].unique().tolist()

    def get_model_summary(self) -> Dict[str, Any]:
        """
        Get summary of actuarial model data.

        Returns:
            Dictionary with model statistics
        """
        summary = {}

        try:
            # Count mortality tables
            tables = self.get_dimension_df('dim_mortality_table')
            if self.session:
                summary['mortality_tables'] = self.session.row_count(tables)
            elif self.backend == 'spark':
                summary['mortality_tables'] = tables.count()
            else:
                summary['mortality_tables'] = len(tables)

            # Count age bands
            age_bands = self.get_dimension_df('dim_age_band')
            if self.session:
                summary['age_bands'] = self.session.row_count(age_bands)
            elif self.backend == 'spark':
                summary['age_bands'] = age_bands.count()
            else:
                summary['age_bands'] = len(age_bands)

            # Count risk classes
            risk_classes = self.get_dimension_df('dim_risk_class')
            if self.session:
                summary['risk_classes'] = self.session.row_count(risk_classes)
            elif self.backend == 'spark':
                summary['risk_classes'] = risk_classes.count()
            else:
                summary['risk_classes'] = len(risk_classes)

        except Exception as e:
            logger.warning(f"Error getting model summary: {e}")
            summary['error'] = str(e)

        return summary
