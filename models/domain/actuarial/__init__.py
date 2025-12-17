"""
Actuarial Model - Mortality, demographics, and risk analysis.

This model provides actuarial analysis capabilities:
- Mortality table management and calculations
- Demographic analysis by geography
- Insurance experience studies
- Present value calculations

Depends on:
- temporal: Time dimension for trend analysis
- geography: Location dimension for geographic analysis
"""
from models.domain.actuarial.model import ActuarialModel

__all__ = ['ActuarialModel']
