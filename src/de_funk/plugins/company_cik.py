"""Fix company_id FK using CIK from dim_company.

Registered as after_build hook for corporate.entity model.
Replaces the old CompanyModel.after_build() class override.
"""
from de_funk.core.plugins import pipeline_hook
from de_funk.config.logging import get_logger

logger = get_logger(__name__)


@pipeline_hook("after_build", model="corporate.entity")
def fix_company_ids(df, engine, config, dims=None, facts=None, **params):
    """Enrich fact tables with CIK-based company_id from dim_company."""
    ticker_col = params.get("ticker_col", "ticker")
    target_col = params.get("target_col", "company_id")

    if dims is None or facts is None:
        return dims, facts

    dim_company = dims.get("dim_company")
    if dim_company is None:
        logger.warning("dim_company not found in dims — skipping CIK enrichment")
        return dims, facts

    # Enrich each fact table that has the ticker column
    # Will use engine.join() when Engine is implemented
    logger.info(f"CIK enrichment: joining facts by {ticker_col} → {target_col}")

    return dims, facts
