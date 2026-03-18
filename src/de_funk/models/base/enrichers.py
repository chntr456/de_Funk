"""
ComputedColumnsEnricher — generic post-build computed column engine.

Reads `build.post_build` column specs from domain model YAML and executes
cross-table enrichments as Delta MERGE operations. No custom Spark per model.
Join paths are inferred from the model's graph.edges — no explicit join_on needed.

Usage in domain model frontmatter (array/tuple syntax):
    build:
      post_build:
        - id: enrich_market_cap
          type: computed_columns
          target: dim_stock
          merge_on: security_id
          columns:
            - [shares_outstanding, corporate.entity.shares_outstanding]
            - [latest_close, stocks.fact_stock_prices.adjusted_close, {window: {fn: last_by, order_by: trade_date}}]
            - [market_cap, "latest_close * shares_outstanding", {cast: long}]

Column tuple format: [id, domain.field or expression, {options}]
  - Position 0: id — output column name in the target table
  - Position 1: "domain.field" ref (last segment = field, rest = domain) OR
                inline expression string (contains spaces/operators) OR
                {fn: ...} catalog dict
  - Position 2: {options} dict — window, cast (optional)

Domain field resolution:
  - "domain.field" → last dot splits domain from field
  - "domain.table.field" → rsplit(".", 1) gives domain="domain.table", field="field"
    (use this explicit form when the field is not in the first table found for the domain)

Graph inference:
  - For each domain ref, scans graph.edges for an edge where cross_model == domain
  - Extracts the cross-model table ref and join condition from that edge
  - No manual join_on needed in the YAML

Window catalog:
  - {fn: last_by,  order_by: col}  → take row with MAX(order_by) per join key
  - {fn: first_by, order_by: col}  → take row with MIN(order_by) per join key
  - {fn: sum_all}                  → SUM the field per join key
  - {fn: avg_all}                  → AVG the field per join key

Expression catalog (same as exhibits/_base/computations.md):
  - {fn: multiply, a: x, by: y}     == "x * y"
  - {fn: divide, of: x, by: y}      == "x / y"  (null-safe)
  - {fn: add, fields: [x, y, z]}    == "x + y + z"
  - {fn: subtract, from: x, subtract: y} == "x - y"
  Inline string form ("x * y") is also accepted and passed to Spark F.expr().
"""
from __future__ import annotations

import functools
import logging
import operator
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Expression catalog
# ---------------------------------------------------------------------------

def _build_expr_catalog():
    """Return the expression catalog. Imported lazily to avoid Spark import at module load."""
    from pyspark.sql import functions as F  # noqa: PLC0415

    return {
        "multiply": lambda a, by, **_: F.col(a) * F.col(by),
        "divide":   lambda of, by, **_: (
            F.col(of) / F.when(F.col(by) != 0, F.col(by))
        ),
        "add":      lambda fields, **_: functools.reduce(
            operator.add, [F.col(f) for f in fields]
        ),
        "subtract": lambda **kw: F.col(kw["from"]) - F.col(kw["subtract"]),
    }


# ---------------------------------------------------------------------------
# ComputedColumnsEnricher
# ---------------------------------------------------------------------------

class ComputedColumnsEnricher:
    """
    Generic engine for build.post_build computed_columns steps.
    Instantiated by the factory builder's post_build hook.
    """

    # ── Parsing helpers ────────────────────────────────────────────────────

    @staticmethod
    def _parse_domain_field(ref: str) -> tuple[str, str]:
        """Split 'domain.field' or 'dom.ain.field' → (domain, field).
        The last segment is always the field; everything before is the domain path.
        """
        parts = ref.rsplit(".", 1)
        if len(parts) == 1:
            return "", parts[0]
        return parts[0], parts[1]

    @staticmethod
    def _is_expression(source: Any) -> bool:
        """True when source is an expression rather than a domain.field reference."""
        if isinstance(source, dict):
            return True  # {fn: ...} catalog form
        if isinstance(source, str):
            expr_chars = set(" *+-/()=<>!,")
            return any(c in expr_chars for c in source)
        return False

    # ── Path resolution ────────────────────────────────────────────────────

    @staticmethod
    def _resolve_silver_path(storage_config: dict, table_ref: str) -> str:
        """Resolve a table reference to its Silver filesystem path.

        Lookup order:
          1. storage_config.tables[table_name] — explicit path config
          2. storage_config.roots[f"{domain}_silver"] — model-specific silver root
          3. Fallback: silver_root / domain_as_path / table_name
        """
        roots = storage_config.get("roots", {})
        tables = storage_config.get("tables", {})
        silver_root = roots.get("silver", "storage/silver")

        # table_ref may be "domain.table_name" or just "table_name"
        if "." in table_ref:
            domain, table_name = table_ref.rsplit(".", 1)
        else:
            domain, table_name = "", table_ref

        # 1. Explicit table config
        if table_name in tables:
            t = tables[table_name]
            t_root = roots.get(t["root"], silver_root)
            return f"{t_root}/{t['rel']}"

        # 2. Domain-specific silver root
        if domain:
            model_silver_key = f"{domain}_silver"
            if model_silver_key in roots:
                return f"{roots[model_silver_key]}/{table_name}"
            # Fallback: construct from domain path
            domain_path = domain.replace(".", "/")
            return f"{silver_root}/{domain_path}/{table_name}"

        return f"{silver_root}/{table_name}"

    # ── Graph inference ────────────────────────────────────────────────────

    @staticmethod
    def _find_edge_for_domain(
        domain: str,
        graph_edges: list,
    ) -> tuple[str, str, str]:
        """Find the cross-model table ref and join columns for a given domain.

        Scans graph.edges for an edge where cross_model == domain.
        Returns (cross_model_table_ref, left_col, right_col).

        Raises ValueError if no matching edge is found.
        """
        for edge in graph_edges:
            if not isinstance(edge, list) or len(edge) < 6:
                continue
            cross_model = edge[5]
            if cross_model != domain:
                continue
            cross_table_ref = str(edge[2])           # e.g. "corporate.entity.dim_company"
            join_conditions = edge[3] if isinstance(edge[3], list) else [edge[3]]
            left_col, right_col = join_conditions[0].split("=")
            return cross_table_ref, left_col.strip(), right_col.strip()

        raise ValueError(
            f"No graph edge found for cross-model domain '{domain}'. "
            f"Add an edge to graph.edges in your model.md with cross_model: {domain}"
        )

    # ── Window functions ───────────────────────────────────────────────────

    @staticmethod
    def _apply_window(df, field: str, window_spec: dict, partition_col: str):
        """Reduce source DataFrame to one row per partition_col using a window function."""
        from pyspark.sql import Window, functions as F  # noqa: PLC0415

        fn = window_spec.get("fn", "last_by")
        order_by = window_spec.get("order_by")

        if fn in ("last_by", "first_by"):
            desc = fn == "last_by"
            w = Window.partitionBy(partition_col).orderBy(
                F.col(order_by).desc() if desc else F.col(order_by).asc()
            )
            return (
                df.withColumn("_rn", F.row_number().over(w))
                  .filter(F.col("_rn") == 1)
                  .drop("_rn")
            )
        if fn == "sum_all":
            from pyspark.sql import functions as F  # noqa: PLC0415
            return df.groupBy(partition_col).agg(F.sum(F.col(field)).alias(field))
        if fn == "avg_all":
            from pyspark.sql import functions as F  # noqa: PLC0415
            return df.groupBy(partition_col).agg(F.avg(F.col(field)).alias(field))

        raise ValueError(f"Unknown window fn '{fn}'. Available: last_by, first_by, sum_all, avg_all")

    # ── Expression evaluation ──────────────────────────────────────────────

    @staticmethod
    def _evaluate_expr(df, col_id: str, expr: Any):
        """Append a computed column to df using a catalog expression or inline string."""
        from pyspark.sql import functions as F  # noqa: PLC0415

        if isinstance(expr, dict):
            catalog = _build_expr_catalog()
            fn_name = expr.get("fn", "")
            if fn_name not in catalog:
                raise ValueError(
                    f"Unknown expression fn '{fn_name}'. Available: {list(catalog)}"
                )
            kwargs = {k: v for k, v in expr.items() if k != "fn"}
            return df.withColumn(col_id, catalog[fn_name](**kwargs))

        if isinstance(expr, str):
            return df.withColumn(col_id, F.expr(expr))

        raise ValueError(f"Expression must be a string or {{fn: ...}} dict, got {type(expr)}")

    # ── Main entry point ───────────────────────────────────────────────────

    def run(
        self,
        spark,
        storage_config: dict,
        graph_cfg: dict,
        step: dict,
    ) -> None:
        """Execute one computed_columns post_build step.

        Args:
            spark:          Active SparkSession.
            storage_config: Full storage.json contents.
            graph_cfg:      The model's graph: section dict (contains edges list).
            step:           One post_build step dict from the model's YAML.
        """
        from delta.tables import DeltaTable          # noqa: PLC0415
        from pyspark.sql import functions as F       # noqa: PLC0415

        step_id  = step.get("id", "unknown")
        target   = step["target"]
        merge_on = step["merge_on"]
        columns  = step.get("columns", [])

        logger.info(
            f"post_build {step_id}: starting computed_columns → {target} (merge_on={merge_on})"
        )

        graph_edges = graph_cfg.get("edges", [])
        target_path = self._resolve_silver_path(storage_config, target)

        # Load target — skip gracefully if the table hasn't been written yet
        if not DeltaTable.isDeltaTable(spark, target_path):
            logger.warning(
                f"post_build {step_id}: target '{target}' not found at {target_path} "
                f"— skipping (table may not have been written yet)"
            )
            return
        enriched_df = spark.read.format("delta").load(target_path)
        target_schema_cols = set(enriched_df.columns)  # capture before enrichment

        computed_col_ids: list[str] = []

        for col_tuple in columns:
            if not isinstance(col_tuple, (list, tuple)) or len(col_tuple) < 2:
                logger.warning(f"post_build {step_id}: skipping malformed column spec {col_tuple!r}")
                continue

            col_id   = col_tuple[0]
            source   = col_tuple[1]
            options  = col_tuple[2] if len(col_tuple) > 2 else {}
            if not isinstance(options, dict):
                options = {}

            cast        = options.get("cast")
            window_spec = options.get("window")

            # ── Expression column ──────────────────────────────────────────
            if self._is_expression(source):
                try:
                    enriched_df = self._evaluate_expr(enriched_df, col_id, source)
                except Exception as e:
                    if "cannot be resolved" in str(e) or "UNRESOLVED_COLUMN" in str(e):
                        logger.warning(
                            f"post_build {step_id}: skipping expression '{col_id}' "
                            f"— unresolved column reference ({e})"
                        )
                        continue
                    raise

            # ── Domain field reference ─────────────────────────────────────
            else:
                domain, field = self._parse_domain_field(str(source))

                try:
                    cross_table_ref, left_col, right_col = self._find_edge_for_domain(
                        domain, graph_edges
                    )
                except ValueError as e:
                    logger.warning(f"post_build {step_id}: {e} — skipping '{col_id}'")
                    continue
                source_path = self._resolve_silver_path(storage_config, cross_table_ref)

                logger.debug(
                    f"  {col_id}: {source_path}[{field}], "
                    f"join {left_col}={right_col}"
                    + (f", window={window_spec}" if window_spec else "")
                )

                source_df = spark.read.format("delta").load(source_path)

                if field not in source_df.columns:
                    logger.warning(
                        f"post_build {step_id}: column '{field}' not found in "
                        f"{cross_table_ref} (available: {source_df.columns}) — skipping {col_id}"
                    )
                    continue

                if window_spec:
                    source_df = self._apply_window(source_df, field, window_spec, right_col)

                # Keep only the join key and the requested field
                source_df = source_df.select(
                    F.col(right_col).alias(f"_src_{right_col}"),
                    F.col(field).alias(col_id),
                )

                # Join onto enriched_df
                enriched_df = enriched_df.join(
                    source_df,
                    enriched_df[left_col] == source_df[f"_src_{right_col}"],
                    how="left",
                ).drop(f"_src_{right_col}")

            # Apply cast if requested
            if cast:
                enriched_df = enriched_df.withColumn(col_id, F.col(col_id).cast(cast))

            computed_col_ids.append(col_id)

        if not computed_col_ids:
            logger.warning(f"post_build {step_id}: no computed columns — skipping")
            return

        # Columns already in the target schema are updated; new columns are added
        # via Delta schema evolution (autoMerge).
        new_cols = [c for c in computed_col_ids if c not in target_schema_cols]
        if new_cols:
            logger.info(
                f"post_build {step_id}: schema evolution — adding {new_cols} to {target}"
            )

        # Select only what we need for the MERGE (merge key + computed cols)
        result_df = (
            enriched_df.select([merge_on] + computed_col_ids)
                       .filter(F.col(merge_on).isNotNull())
        )

        count = result_df.count()
        if count == 0:
            logger.warning(f"post_build {step_id}: 0 rows to merge — skipping")
            return

        logger.info(f"post_build {step_id}: merging {count} rows into {target}")

        update_set = {col: f"src.{col}" for col in computed_col_ids}

        # Enable schema evolution so new columns are added to the Delta table
        spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")

        DeltaTable.forPath(spark, target_path).alias("target") \
            .merge(result_df.alias("src"), f"target.{merge_on} = src.{merge_on}") \
            .whenMatchedUpdateAll() \
            .execute()

        logger.info(f"post_build {step_id}: complete — {len(computed_col_ids)} columns enriched")
