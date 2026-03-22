"""
Typed data classes mirroring domain YAML frontmatter structure.

These dataclasses provide IDE completion, validation at parse time,
and documentation of every field in the YAML configs. They replace
raw Dict[str, Any] passing throughout the codebase.

Domain configs (from markdown):
    DomainModelConfig, TableConfig, SourceConfig, SchemaField,
    EdgeSpec, MeasureDef, AliasSpec, EnrichSpec, GraphSpec,
    BuildSpec, MeasuresSpec, HookDef, PipelineStep, HooksConfig,
    ModelStorageSpec, PhaseSpec, BaseTemplate

Provider configs (from data source markdown):
    ProviderConfig, EndpointConfig, EndpointSchemaField
"""
from __future__ import annotations
from dataclasses import dataclass, field as dc_field
from typing import Any, Optional


# ── Atomic types ─────────────────────────────────────────

@dataclass
class SchemaField:
    """One column in a table schema. Parsed from [name, type, nullable, desc, {opts}]."""
    name: str
    type: str
    nullable: bool = True
    description: str = ""
    derived: Optional[str] = None
    fk: Optional[str] = None
    format: Optional[str] = None


@dataclass
class EdgeSpec:
    """One graph edge. Parsed from [name, from, to, [keys], cardinality, domain, ...]."""
    name: str
    from_table: str
    to_table: str
    join_keys: list[str] = dc_field(default_factory=list)
    cardinality: str = "many_to_one"
    target_domain: Optional[str] = None
    optional: bool = False


@dataclass
class MeasureDef:
    """One measure definition. Parsed from [name, agg, field, label, {opts}]."""
    name: str
    aggregation: str
    field: str | dict = ""
    label: str = ""
    format: Optional[str] = None
    options: dict = dc_field(default_factory=dict)


@dataclass
class AliasSpec:
    """One source alias. Parsed from [target_column, expression]."""
    target_column: str
    expression: str


@dataclass
class EnrichSpec:
    """Join-based enrichment on a table."""
    from_table: str
    join: list[str] = dc_field(default_factory=list)
    columns: list[str] = dc_field(default_factory=list)


@dataclass
class HookDef:
    """One hook definition — references a Python function by dotted path."""
    fn: str
    params: dict = dc_field(default_factory=dict)


@dataclass
class PipelineStep:
    """One step in a config-driven pipeline."""
    op: str
    fn: Optional[str] = None
    params: dict = dc_field(default_factory=dict)


# ── Nested specs ─────────────────────────────────────────

@dataclass
class PhaseSpec:
    """One build phase — lists tables to build in this phase."""
    tables: list[str] = dc_field(default_factory=list)


@dataclass
class ModelStorageSpec:
    """Storage configuration for a domain model."""
    format: str = "delta"
    silver_root: Optional[str] = None


@dataclass
class BuildSpec:
    """Build configuration for a domain model."""
    sort_by: list[str] = dc_field(default_factory=list)
    optimize: bool = True
    partitions: list[str] = dc_field(default_factory=list)
    phases: dict[str, PhaseSpec] = dc_field(default_factory=dict)


@dataclass
class GraphSpec:
    """Graph edges and paths for a domain model."""
    edges: list[EdgeSpec] = dc_field(default_factory=list)
    paths: dict[str, Any] = dc_field(default_factory=dict)


@dataclass
class MeasuresSpec:
    """Measure definitions for a domain model."""
    simple: list[MeasureDef] = dc_field(default_factory=list)
    computed: list[MeasureDef] = dc_field(default_factory=list)


@dataclass
class HooksConfig:
    """Build hooks declared in YAML frontmatter."""
    pre_build: list[HookDef] = dc_field(default_factory=list)
    before_build: list[HookDef] = dc_field(default_factory=list)
    after_build: list[HookDef] = dc_field(default_factory=list)
    post_build: list[HookDef] = dc_field(default_factory=list)


# ── Config containers ────────────────────────────────────

@dataclass
class TableConfig:
    """Parsed from tables/*.md frontmatter."""
    table: str = ""
    table_type: str = "dimension"
    schema: list[SchemaField] = dc_field(default_factory=list)
    primary_key: list[str] = dc_field(default_factory=list)
    unique_key: list[str] = dc_field(default_factory=list)
    partition_by: list[str] = dc_field(default_factory=list)
    measures: list[MeasureDef] = dc_field(default_factory=list)
    enrich: list[EnrichSpec] = dc_field(default_factory=list)
    pipeline: list[PipelineStep] = dc_field(default_factory=list)
    extends: Optional[str] = None
    source_file: Optional[str] = None


@dataclass
class SourceConfig:
    """Parsed from sources/**/*.md frontmatter."""
    source: str = ""
    maps_to: str = ""
    from_ref: str = ""
    aliases: list[AliasSpec] = dc_field(default_factory=list)
    domain_source: Optional[str] = None
    filter: list[str] = dc_field(default_factory=list)
    discriminator: Optional[str] = None
    extends: Optional[str] = None
    source_file: Optional[str] = None


@dataclass
class DomainModelConfig:
    """Parsed from model.md frontmatter + auto-discovered tables/sources/views."""
    model: str = ""
    version: str = "1.0"
    description: str = ""
    extends: list[str] = dc_field(default_factory=list)
    depends_on: list[str] = dc_field(default_factory=list)
    status: str = "active"
    sources_from: Optional[str] = None

    storage: ModelStorageSpec = dc_field(default_factory=ModelStorageSpec)
    graph: GraphSpec = dc_field(default_factory=GraphSpec)
    build: BuildSpec = dc_field(default_factory=BuildSpec)
    measures: MeasuresSpec = dc_field(default_factory=MeasuresSpec)
    hooks: HooksConfig = dc_field(default_factory=HooksConfig)
    metadata: dict = dc_field(default_factory=dict)

    tables: dict[str, TableConfig] = dc_field(default_factory=dict)
    sources: dict[str, SourceConfig] = dc_field(default_factory=dict)
    views: dict[str, Any] = dc_field(default_factory=dict)

    source_file: Optional[str] = None


@dataclass
class BaseTemplate:
    """Reusable base template from domains/_base/."""
    type: str = "domain-base"
    model: str = ""
    version: str = "1.0"
    description: str = ""
    extends: Optional[str] = None
    canonical_fields: list[SchemaField] = dc_field(default_factory=list)
    tables: dict[str, TableConfig] = dc_field(default_factory=dict)
    depends_on: list[str] = dc_field(default_factory=list)
    source_file: Optional[str] = None


# ── Provider / Endpoint configs ──────────────────────────

@dataclass
class EndpointSchemaField:
    """One field in an endpoint schema — different from domain SchemaField."""
    name: str = ""
    type: str = "string"
    source_field: str = ""
    nullable: bool = True
    description: str = ""
    transform: Optional[str] = None
    coerce: Optional[str] = None
    default: Optional[Any] = None


@dataclass
class EndpointConfig:
    """Parsed from Endpoints/**/*.md frontmatter."""
    endpoint_id: str = ""
    provider: str = ""
    method: str = "GET"
    endpoint_pattern: str = ""
    format: str = "json"
    auth: str = "inherit"
    response_key: Optional[str] = None
    default_query: dict = dc_field(default_factory=dict)
    required_params: list[str] = dc_field(default_factory=list)
    pagination_type: str = "none"
    bulk_download: bool = False
    download_method: str = "json"
    json_structure: str = "object"
    raw_schema: list[list] = dc_field(default_factory=list)
    schema: list[EndpointSchemaField] = dc_field(default_factory=list)
    bronze: Optional[str] = None
    partitions: list[str] = dc_field(default_factory=list)
    write_strategy: str = "upsert"
    key_columns: list[str] = dc_field(default_factory=list)
    date_column: Optional[str] = None
    domain: str = ""
    data_tags: list[str] = dc_field(default_factory=list)
    status: str = "active"
    update_cadence: str = ""
    source_file: Optional[str] = None


@dataclass
class ProviderConfig:
    """Parsed from Providers/*.md frontmatter."""
    provider_id: str = ""
    provider: str = ""
    api_type: str = "rest"
    base_url: str = ""
    auth_model: str = "api-key"
    env_api_key: str = ""
    rate_limit_per_sec: float = 1.0
    default_headers: dict = dc_field(default_factory=dict)
    provider_settings: dict = dc_field(default_factory=dict)
    endpoints: list[str] = dc_field(default_factory=list)
    models: list[str] = dc_field(default_factory=list)
    category: str = "public"
    data_domains: list[str] = dc_field(default_factory=list)
    data_tags: list[str] = dc_field(default_factory=list)
    status: str = "active"
    source_file: Optional[str] = None
