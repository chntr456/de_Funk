"""
Foundation models - core reference dimensions.

Foundation models have no dependencies and provide shared
reference data that domain models can join against:

- temporal: Time and calendar dimensions (dates, weeks, months, quarters, years)

All domain models depend on one or more foundation models.

NOTE: This is a compatibility shim. New code should import from:
  models.domains.foundation.temporal.model
"""
# Re-export from canonical location for backwards compatibility
try:
    from models.domains.foundation.temporal.model import TemporalModel
    __all__ = ['TemporalModel']
except ImportError:
    # During testing or if module not available
    __all__ = []
