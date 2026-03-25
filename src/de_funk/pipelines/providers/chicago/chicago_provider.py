"""
Chicago Data Portal — config-driven Socrata provider.

No subclass needed. All behavior from SocrataBaseProvider + markdown configs.

Usage:
    from de_funk.pipelines.providers.chicago import create_chicago_provider
    provider = create_chicago_provider(spark, docs_path)
"""
from __future__ import annotations

from typing import Optional
from pathlib import Path

from de_funk.pipelines.base.socrata_provider import SocrataBaseProvider, create_socrata_provider


def create_chicago_provider(
    spark=None,
    docs_path: Optional[Path] = None,
    storage_path: Optional[Path] = None,
    **kwargs,
) -> SocrataBaseProvider:
    """Create a Chicago Data Portal provider (config-driven)."""
    return create_socrata_provider(
        provider_id="chicago",
        spark=spark,
        docs_path=docs_path,
        storage_path=storage_path,
        **kwargs,
    )


# Backward compat alias
ChicagoProvider = SocrataBaseProvider
