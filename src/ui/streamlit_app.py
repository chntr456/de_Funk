# src/ui/streamlit_app.py
from __future__ import annotations

# --- import path bootstrap: ensure repo root is on sys.path BEFORE other imports ---
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[2]  # repo/
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# --- Streamlit must be first command: set page config here ---
import streamlit as st
st.set_page_config(page_title="Company Model Explorer", layout="wide")

"""
Streamlit starter UI for exploring the Company model (Spark-based).

Run from repo root:
    streamlit run src/ui/streamlit_app.py

Architecture:
- This app uses Spark + ModelSession for direct model/table exploration
- For DuckDB-powered notebooks (10-100x faster), use:
    streamlit run src/ui/notebook_app_professional.py

Notes:
- This UI reads what's already in bronze/silver. Run your ingestion script separately to refresh data.
- We avoid passing Spark/RepoContext into cached functions to prevent Streamlit hashing Spark objects.
- Requires pyspark installed
"""

import datetime as dt
from typing import List

from pyspark.sql import functions as F

from src.orchestration.context import RepoContext
from src.model.api.session import ModelSession
from src.model.api.services import PricesAPI, NewsAPI, CompanyAPI


# ---------------------- cached factories (no-arg to avoid hashing Spark) ----------------------

@st.cache_resource
def get_ctx() -> RepoContext:
    """One RepoContext & SparkSession for the whole Streamlit process."""
    return RepoContext.from_repo_root()

@st.cache_resource
def get_model_session() -> ModelSession:
    """Build ModelSession using the cached RepoContext (no args → no hashing of Spark)."""
    ctx = get_ctx()
    # Optionally quiet Spark logs a bit in UI sessions:
    try:
        ctx.spark.sparkContext.setLogLevel("ERROR")
        ctx.spark.conf.set("spark.ui.enabled", "false")
    except Exception:
        pass
    return ModelSession(ctx.spark, ctx.repo, ctx.storage)

@st.cache_data(show_spinner=False)
def cached_active_tickers(limit: int | None = 2000) -> List[str]:
    """Cache the active ticker universe as a plain Python list for a snappy multiselect."""
    ms = get_model_session()
    company = CompanyAPI(ms)
    df = company.active_universe(limit=limit)
    return [r["ticker"] for r in df.collect()]


# ------------------------------------------- UI Class -------------------------------------------

class CompanyExplorerApp:
    """
    Minimal, pragmatic Streamlit UI to explore your bronze/silver data.
    - Filters: date range, tickers, “only matched to company” toggle
    - Tabs: Prices, News
    - Uses your ModelSession & Services (no extra paths/config scattered)
    """

    def __init__(self):
        self.ctx = get_ctx()
        self.ms = get_model_session()
        self.prices = PricesAPI(self.ms)
        self.news = NewsAPI(self.ms)
        self.company = CompanyAPI(self.ms)

        # sensible defaults
        self.default_start = dt.date(2024, 1, 1)
        self.default_end = dt.date(2024, 1, 5)

    # ------------------------------- helpers (filters & widgets) -------------------------------

    def _date_inputs(self):
        c1, c2 = st.columns(2)
        with c1:
            start = st.date_input("Start date", value=self.default_start, key="start_dt")
        with c2:
            end = st.date_input("End date", value=self.default_end, key="end_dt")
        if start > end:
            st.warning("Start date is after end date; swapping.")
            start, end = end, start
        return start.isoformat(), end.isoformat()

    def _ticker_multiselect(self) -> List[str]:
        tickers = cached_active_tickers(limit=2000)
        return st.multiselect("Tickers (optional)", options=tickers, default=[])

    # ---------------------------------------------- tabs ----------------------------------------------

    def _tab_prices(self, date_from: str, date_to: str):
        st.subheader("📈 Prices (silver path: prices_with_company)")
        only_matched = st.checkbox("Only tickers with company metadata", value=False, key="prices_only_matched")
        selected = self._ticker_multiselect()

        df = self.prices.prices_with_company_df(date_from, date_to, only_matched=only_matched)
        if selected:
            df = df.where(F.col("ticker").isin(selected))

        st.caption("Sample rows")
        st.dataframe(df.limit(200).toPandas())

        # Quick line for the first selected ticker (if any)
        if selected:
            ticker = selected[0]
            st.caption(f"Close price for {ticker}")
            pdf = (
                df.where(F.col("ticker") == ticker)
                  .select("trade_date", "close")
                  .orderBy("trade_date")
                  .toPandas()
            )
            if not pdf.empty:
                st.line_chart(pdf, x="trade_date", y="close")
            else:
                st.info("No rows for selected ticker & date range.")

    def _tab_news(self, date_from: str, date_to: str):
        st.subheader("📰 News (silver path: news_with_company)")
        only_matched = st.checkbox("Only tickers with company metadata", value=True, key="news_only_matched")
        selected = self._ticker_multiselect()

        df = self.news.news_with_company_df(date_from, date_to, only_matched=only_matched)
        if selected:
            df = df.where(F.col("ticker").isin(selected))

        st.caption("Sample rows")
        st.dataframe(
            df.select("publish_date", "ticker", "company_name", "title", "source", "sentiment")
              .orderBy("publish_date", "ticker")
              .limit(200)
              .toPandas()
        )

        # Simple “top sources” bar
        top = df.groupBy("source").count().orderBy(F.desc("count")).limit(10).toPandas()
        st.caption("Top sources")
        if not top.empty:
            top = top.sort_values("count", ascending=False)
            st.bar_chart(top.set_index("source")["count"])
        else:
            st.info("No news rows in the selected range/filters.")

    # ------------------------------------------------ main ------------------------------------------------

    def run(self):
        st.title("Company Model Explorer")

        with st.sidebar:
            st.markdown("### Filters")
            date_from, date_to = self._date_inputs()
            st.caption("The UI reads what’s already in bronze/silver. Use your ingestion script to refresh data.")

        tab1, tab2 = st.tabs(["Prices", "News"])
        with tab1:
            self._tab_prices(date_from, date_to)
        with tab2:
            self._tab_news(date_from, date_to)


# ------------------------------------------- entrypoint -------------------------------------------

def main():
    CompanyExplorerApp().run()

if __name__ == "__main__":
    # Prefer: streamlit run src/ui/streamlit_app.py
    main()
