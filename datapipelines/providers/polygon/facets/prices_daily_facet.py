from __future__ import annotations
from typing import Iterable, List, Tuple
from pyspark.sql import SparkSession
from .polygon_base_facet import PolygonFacet
from orchestration.common.spark_df_utils import epoch_ms_to_date

class PricesDailyFacet(PolygonFacet):
    name = "prices_daily"

    RAW_SCHEMA_SPEC: List[Tuple[str, str]] = [
        ("t","long"), ("o","double"), ("h","double"), ("l","double"), ("c","double"),
        ("v","double"), ("vw","double"), ("T","string")  # we will inject T below
    ]
    RENAME_MAP = {"o":"open","h":"high","l":"low","c":"close","v":"volume","vw":"volume_weighted","T":"ticker"}
    OUTPUT_SCHEMA = [
        ("trade_date","date"), ("ticker","string"),
        ("open","double"), ("high","double"), ("low","double"), ("close","double"),
        ("volume_weighted","double"), ("volume","double")
    ]
    DERIVED = {"trade_date": lambda df: epoch_ms_to_date("t")}

    def __init__(self, spark: SparkSession, *, tickers: List[str], date_from: str, date_to: str, mult: int = 1, timespan: str = "day"):
        super().__init__(spark, tickers=tickers, date_from=date_from, date_to=date_to, mult=mult, timespan=timespan)
        self._call_contexts: List[dict] = []  # keeps per-call metadata (e.g., ticker) in order

    def calls(self) -> Iterable[dict]:
        self._call_contexts = []
        for t in self.tickers:
            params = {"ticker": t, "from": self.date_from, "to": self.date_to,
                      "mult": self.extra.get("mult", 1), "timespan": self.extra.get("timespan","day")}
            self._call_contexts.append({"ticker": t})
            yield {"ep_name": "prices_daily", "params": params}

    # --- IMPORTANT: enrich rows with ticker before passing to base normalize ---
    def normalize(self, raw_batches: List[List[dict]]):
        enriched: List[List[dict]] = []
        # zip raw batches to call contexts by position
        for i, rows in enumerate(raw_batches):
            ctx_ticker = None
            if i < len(self._call_contexts):
                ctx_ticker = self._call_contexts[i].get("ticker")
            if ctx_ticker:
                rows = [{**r, "T": ctx_ticker} for r in (rows or [])]
            enriched.append(rows or [])
        # now use the base implementation
        return super().normalize(enriched)
