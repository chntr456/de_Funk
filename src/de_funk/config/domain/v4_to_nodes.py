"""
V4-to-V3 config translator for domain model builds.

Converts v4 model config (tables + sources + build phases) into
v3-compatible config with synthesized `graph.nodes` that GraphBuilder
can process directly.

The translator produces one graph.node entry per table by combining:
- Source config → node `from` (Bronze path) + `select` (alias dict)
- Table config → node `derive` (from schema {derived:}), `filters`, `unique_key`
- Enrich specs → node `join` entries (dimension lookups)
- Seed/static → flagged for custom_node_loading in V4Model
"""

import logging
from typing import Dict, Any, List, Optional

from de_funk.config.domain.sources import (
    group_sources_by_target,
    process_source_config,
)
from de_funk.config.domain.build import (
    parse_build_config,
    get_table_build_flags,
    extract_seed_data,
    process_enrich_specs,
)

logger = logging.getLogger(__name__)


def translate_v4_config(v4_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translate a v4 model config into v3-compatible format with graph.nodes.

    The output preserves all v4-specific keys (tables, sources, build, views)
    and ADDS a synthesized `graph.nodes` dict so GraphBuilder can process it.

    Args:
        v4_config: Config dict from DomainConfigLoaderV4.load_model_config()

    Returns:
        Translated config dict with graph.nodes added
    """
    config = dict(v4_config)
    tables = config.get("tables", {})
    sources = config.get("sources", {})

    # Process all sources to get select expressions
    processed_sources = {}
    for name, src in sources.items():
        processed_sources[name] = process_source_config(dict(src))

    # Group sources by their target table
    by_target = group_sources_by_target(processed_sources)

    # Parse build config for phase ordering
    build_config = parse_build_config(config)

    # Build ordered table list from phases
    ordered_tables = _get_phase_ordered_tables(build_config, tables)

    # Synthesize graph.nodes
    nodes = {}
    for table_name in ordered_tables:
        table_config = tables.get(table_name, {})
        if not isinstance(table_config, dict):
            continue

        node = _synthesize_node(
            table_name, table_config, by_target.get(table_name, [])
        )
        if node:
            nodes[table_name] = node

    # Inject synthesized nodes into config
    graph = config.get("graph", {})
    if not isinstance(graph, dict):
        graph = {}
    graph["nodes"] = nodes
    config["graph"] = graph

    # Store build metadata for V4Model
    config["_v4_build"] = build_config
    config["_v4_sources_by_target"] = by_target

    return config


def _get_phase_ordered_tables(
    build_config: Dict[str, Any],
    tables: Dict[str, Any],
) -> List[str]:
    """
    Get tables in build-phase order (dims before facts).

    If phases are defined, returns tables in phase order.
    Otherwise, returns dims first, then facts (alphabetical within each group).
    """
    phases = build_config.get("phases", [])

    if phases:
        ordered = []
        for phase in sorted(phases, key=lambda p: p["phase_num"]):
            for t in phase["tables"]:
                if t not in ordered and t in tables:
                    ordered.append(t)
        # Add any tables not in phases (shouldn't happen, but be safe)
        for t in tables:
            if t not in ordered:
                ordered.append(t)
        return ordered

    # No phases — dims first, then facts
    dims = sorted(t for t in tables if t.startswith("dim_"))
    facts = sorted(t for t in tables if t.startswith("fact_"))
    others = sorted(t for t in tables if t not in dims and t not in facts)
    return dims + others + facts


def _synthesize_node(
    table_name: str,
    table_config: Dict[str, Any],
    matching_sources: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Synthesize a single v3 graph.node from v4 table + source configs.

    Args:
        table_name: Name of the table (e.g., "dim_parcel")
        table_config: Table config from v4
        matching_sources: Source configs that map_to this table

    Returns:
        V3-compatible node dict, or None if cannot be built
    """
    flags = get_table_build_flags(table_config)

    # Seed/static tables — mark for custom_node_loading
    if flags["static"]:
        seed_data = extract_seed_data(table_config)
        return {
            "from": "__seed__",
            "type": _table_type(table_name),
            "_v4_seed": True,
            "_v4_seed_data": seed_data,
            "_v4_schema": table_config.get("schema", []),
            "primary_key": flags["primary_key"],
            "unique_key": flags["unique_key"],
        }

    # Generated tables — mark for custom_node_loading
    if flags["generated"]:
        return {
            "from": "__generated__",
            "type": _table_type(table_name),
            "_v4_generated": True,
            "_v4_table_config": table_config,
            "primary_key": flags["primary_key"],
            "unique_key": flags["unique_key"],
        }

    # Standard table — needs at least one source
    if not matching_sources:
        # Table has no source — might inherit from parent or be enrichment-only
        # Check if table has a `from` key directly (some v4 tables do)
        direct_from = table_config.get("from")
        if direct_from:
            node = _build_node_from_table(table_name, table_config, direct_from)
            return node
        logger.debug(
            f"Table '{table_name}' has no matching source and no 'from' — "
            f"will need custom_node_loading or cross-model reference"
        )
        return None

    # Single source → straightforward node
    if len(matching_sources) == 1:
        source = matching_sources[0]
        return _build_node_from_source(table_name, table_config, source, flags)

    # Multiple sources → UNION node (handled by V4Model.custom_node_loading)
    return _build_union_node(table_name, table_config, matching_sources, flags)


def _build_node_from_source(
    table_name: str,
    table_config: Dict[str, Any],
    source: Dict[str, Any],
    flags: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a v3 node from a single source mapping."""
    # Convert source `from` to v3 bronze path format
    from_spec = _normalize_from(source.get("from", ""))

    # Convert aliases to v3 select dict: {canonical_name: expression}
    select = _aliases_to_select_dict(source.get("aliases", []))

    # Add discriminator columns to select
    if source.get("domain_source"):
        select["domain_source"] = source["domain_source"]
    if source.get("entry_type"):
        select["entry_type"] = f"'{source['entry_type']}'"
    if source.get("event_type"):
        select["event_type"] = f"'{source['event_type']}'"

    # Extract derive expressions from table schema {derived:} options
    derive = _extract_derive_from_schema(table_config.get("schema", []))

    # Also include derivations map if present
    derivations = table_config.get("derivations", {})
    if isinstance(derivations, dict):
        derive.update(derivations)

    # Build enrich → join specs
    join_specs = _enrich_to_join_specs(table_config)

    node = {
        "from": from_spec,
        "type": _table_type(table_name),
    }

    if select:
        node["select"] = select
    if flags.get("filters"):
        node["filters"] = flags["filters"]
    if derive:
        node["derive"] = derive
    if flags.get("unique_key"):
        node["unique_key"] = flags["unique_key"]
    elif flags.get("primary_key"):
        node["unique_key"] = flags["primary_key"]
    if join_specs:
        node["join"] = join_specs

    # Store v4-specific metadata for advanced processing
    if source.get("transform"):
        node["_v4_transform"] = source["transform"]
        if source.get("_unpivot_plan"):
            node["_v4_unpivot_plan"] = source["_unpivot_plan"]

    return node


def _build_node_from_table(
    table_name: str,
    table_config: Dict[str, Any],
    from_spec: str,
) -> Dict[str, Any]:
    """Build a v3 node from a table config that has a direct `from` key."""
    from_normalized = _normalize_from(from_spec)
    flags = get_table_build_flags(table_config)
    derive = _extract_derive_from_schema(table_config.get("schema", []))

    node = {
        "from": from_normalized,
        "type": _table_type(table_name),
    }

    if flags.get("filters"):
        node["filters"] = flags["filters"]
    if derive:
        node["derive"] = derive
    if flags.get("unique_key"):
        node["unique_key"] = flags["unique_key"]
    elif flags.get("primary_key"):
        node["unique_key"] = flags["primary_key"]

    return node


def _build_union_node(
    table_name: str,
    table_config: Dict[str, Any],
    sources: List[Dict[str, Any]],
    flags: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a UNION node for tables with multiple sources."""
    derive = _extract_derive_from_schema(table_config.get("schema", []))

    return {
        "from": "__union__",
        "type": _table_type(table_name),
        "_v4_union": True,
        "_v4_union_sources": sources,
        "_v4_schema": table_config.get("schema", []),
        "derive": derive if derive else {},
        "unique_key": flags.get("unique_key") or flags.get("primary_key", []),
    }


def _normalize_from(from_spec: str) -> str:
    """
    Normalize a v4 `from` spec to v3 format.

    v4: "bronze.cook_county_parcel_sales"  → "bronze.cook_county_parcel_sales"
    v4: "bronze.alpha_vantage.listing_status" → "bronze.alpha_vantage.listing_status"
    v4: "silver.temporal.dim_calendar" → "temporal.dim_calendar"
    """
    if not from_spec:
        return from_spec

    parts = from_spec.split(".", 1)
    if parts[0] == "silver" and len(parts) > 1:
        return parts[1]  # Strip "silver." prefix for GraphBuilder
    return from_spec


def _aliases_to_select_dict(aliases: List[List]) -> Dict[str, str]:
    """
    Convert v4 alias pairs to v3 select dict.

    v4 aliases: [["parcel_id", "LPAD(pin, 14, '0')"], ["sale_date", "sale_date"]]
    v3 select:  {"parcel_id": "LPAD(pin, 14, '0')", "sale_date": "sale_date"}
    """
    select = {}
    for alias in aliases:
        if isinstance(alias, list) and len(alias) >= 2:
            canonical_name = alias[0]
            expression = str(alias[1])
            select[canonical_name] = expression
    return select


def _extract_derive_from_schema(schema: List) -> Dict[str, str]:
    """
    Extract {derived: "expr"} from v4 schema column definitions.

    Schema format: [name, type, nullable, description, {options}]
    Options may contain: {derived: "SQL_EXPRESSION"}

    Returns:
        Dict of column_name → derive expression
    """
    derive = {}
    for col in schema:
        if not isinstance(col, list) or len(col) < 5:
            continue
        options = col[4] if len(col) > 4 else None
        if isinstance(options, dict) and "derived" in options:
            derive[col[0]] = options["derived"]
    return derive


def _enrich_to_join_specs(table_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert v4 enrich specs to v3 join format.

    v4 enrich: [{join: dim_x, on: [col1=col2], fields: [field1]}]
    v3 join:   [{table: dim_x, on: ["col1=col2"], type: "left"}]
    """
    enrich_specs = process_enrich_specs(table_config)
    join_specs = []

    for spec in enrich_specs:
        if spec["type"] == "lookup":
            # Compact dimension lookup
            on_pairs = spec.get("on", [])
            on_strings = [f"{left}={right}" for left, right in on_pairs]
            join_specs.append({
                "table": spec["join"],
                "on": on_strings,
                "type": "left",
                "_v4_fields": spec.get("fields", []),
            })
        elif spec["type"] == "join":
            # Standard enrich from fact table
            on_pairs = spec.get("join", [])
            on_strings = [f"{left}={right}" for left, right in on_pairs]
            join_specs.append({
                "table": spec["from"],
                "on": on_strings,
                "type": "left",
                "filter": spec.get("filter"),
                "_v4_columns": spec.get("columns", []),
            })

    return join_specs


def _table_type(table_name: str) -> str:
    """Infer table type from naming convention."""
    if table_name.startswith("dim_"):
        return "dimension"
    elif table_name.startswith("fact_"):
        return "fact"
    return "other"
