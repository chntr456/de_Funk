"""Generate dim_calendar programmatically (no Bronze source).

Registered as custom_node_loading hook for the temporal model.
Generates a calendar dimension table covering configurable date range.
"""
from de_funk.core.plugins import pipeline_hook
from de_funk.config.logging import get_logger

logger = get_logger(__name__)


@pipeline_hook("custom_node_loading", model="temporal")
def generate_calendar(df, engine, config, node_id=None, node_config=None, **params):
    """Generate dim_calendar if this is the calendar node."""
    if node_id != "dim_calendar":
        return None

    start = params.get("start", "2000-01-01")
    end = params.get("end", "2050-12-31")
    logger.info(f"Generating dim_calendar: {start} to {end}")

    # Delegate to engine for backend-specific calendar generation
    # Engine.execute_sql handles Spark vs DuckDB differences
    # For now, return None — will be implemented when Engine is ready
    return None
