"""
Macro model - BACKWARD COMPATIBILITY LAYER.

DEPRECATED: Import from models.domains.economic.macro instead.

Example:
    # Old (deprecated)
    from models.domain.macro import MacroModel

    # New (recommended)
    from models.domains.economic.macro import MacroModel
"""

from models.domains.economic.macro import MacroModel

__all__ = ['MacroModel']
