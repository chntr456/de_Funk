"""
Options model - BACKWARD COMPATIBILITY LAYER.

DEPRECATED: Import from models.domains.securities.options instead.

Example:
    # Old (deprecated)
    from models.domain.options import OptionsModel

    # New (recommended)
    from models.domains.securities.options import OptionsModel
"""

from models.domains.securities.options import (
    OptionsModel,
    BlackScholes,
    OptionType,
    OptionParams,
    OptionResult,
    OptionsMeasures,
)

__all__ = [
    'OptionsModel',
    'BlackScholes',
    'OptionType',
    'OptionParams',
    'OptionResult',
    'OptionsMeasures',
]
