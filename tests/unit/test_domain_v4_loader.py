"""
Domain V4 Loader Tests — test suite for the multi-file domain config system.

Tests are organized by phase to match the implementation plan in
docs/proposals/015-domain-model-v4-implementation.md.

Usage:
    pytest tests/unit/test_domain_v4_loader.py -v
    pytest tests/unit/test_domain_v4_loader.py -v -k "phase0"
    pytest tests/unit/test_domain_v4_loader.py -v -k "phase1"
"""

import sys
from pathlib import Path

# Bootstrap repo imports
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from de_funk.utils.repo import setup_repo_imports
setup_repo_imports()

import pytest
import yaml


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "domain_v4"


@pytest.fixture
def fixtures_dir():
    """Path to domain_v4 test fixtures."""
    return FIXTURES_DIR


def _parse_front_matter(file_path: Path) -> dict:
    """Minimal front matter parser for fixture validation."""
    import re
    content = file_path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    return yaml.safe_load(match.group(1)) or {}


# ===========================================================================
# Phase 0: Fixture validation — all test markdown files parse correctly
# ===========================================================================

class TestPhase0FixtureValidation:
    """Verify test fixtures are well-formed before testing loader code."""

    def test_fixtures_dir_exists(self, fixtures_dir):
        assert fixtures_dir.exists(), f"Fixtures dir not found: {fixtures_dir}"

    def test_all_fixture_files_parse(self, fixtures_dir):
        """Every .md file in fixtures should have valid YAML front matter."""
        md_files = list(fixtures_dir.rglob("*.md"))
        assert len(md_files) >= 10, f"Expected 10+ fixture files, found {len(md_files)}"

        errors = []
        for md_file in md_files:
            try:
                config = _parse_front_matter(md_file)
                if not config:
                    errors.append(f"{md_file.name}: no front matter")
                elif "type" not in config:
                    errors.append(f"{md_file.name}: missing 'type' key")
            except Exception as e:
                errors.append(f"{md_file.name}: {e}")

        assert not errors, f"Fixture parse errors:\n" + "\n".join(errors)

    def test_file_type_distribution(self, fixtures_dir):
        """Verify fixtures cover all 5 file types."""
        type_counts = {}
        for md_file in fixtures_dir.rglob("*.md"):
            config = _parse_front_matter(md_file)
            file_type = config.get("type", "unknown")
            type_counts[file_type] = type_counts.get(file_type, 0) + 1

        assert "domain-base" in type_counts, "Missing domain-base fixtures"
        assert "domain-model" in type_counts, "Missing domain-model fixtures"
        assert "domain-model-table" in type_counts, "Missing domain-model-table fixtures"
        assert "domain-model-source" in type_counts, "Missing domain-model-source fixtures"
        assert "domain-model-view" in type_counts, "Missing domain-model-view fixtures"
        assert "reference" in type_counts, "Missing reference fixtures"

    def test_base_template_has_required_keys(self, fixtures_dir):
        """Base template should have canonical_fields, tables, subsets."""
        config = _parse_front_matter(fixtures_dir / "_base/simple/base_template.md")
        assert config["type"] == "domain-base"
        assert "canonical_fields" in config
        assert "tables" in config
        assert "subsets" in config
        assert "auto_edges" in config

    def test_subset_children_have_required_keys(self, fixtures_dir):
        """Subset children should have subset_of, subset_value, canonical_fields."""
        for child_name in ["subset_a.md", "subset_b.md"]:
            config = _parse_front_matter(
                fixtures_dir / f"_base/simple/child/{child_name}"
            )
            assert config["type"] == "domain-base"
            assert "subset_of" in config, f"{child_name} missing subset_of"
            assert "subset_value" in config, f"{child_name} missing subset_value"
            assert "canonical_fields" in config, f"{child_name} missing canonical_fields"
            assert "measures" in config, f"{child_name} missing measures"

    def test_model_has_required_keys(self, fixtures_dir):
        """Domain model should have extends, depends_on, graph, build."""
        config = _parse_front_matter(fixtures_dir / "models/test_model/model.md")
        assert config["type"] == "domain-model"
        assert config["model"] == "test_model"
        assert "extends" in config
        assert "depends_on" in config
        assert "graph" in config
        assert "build" in config
        assert "measures" in config

    def test_table_files_have_required_keys(self, fixtures_dir):
        """Table files should have table, extends, table_type."""
        for table_file in (fixtures_dir / "models/test_model/tables").glob("*.md"):
            config = _parse_front_matter(table_file)
            assert config["type"] == "domain-model-table", f"{table_file.name}"
            assert "table" in config, f"{table_file.name} missing table"
            assert "extends" in config, f"{table_file.name} missing extends"
            assert "table_type" in config, f"{table_file.name} missing table_type"

    def test_source_files_have_required_keys(self, fixtures_dir):
        """Source files should have maps_to, from, aliases."""
        source_dir = fixtures_dir / "models/test_model/sources"
        source_files = list(source_dir.rglob("*.md"))
        assert len(source_files) >= 2, f"Expected 2+ source files, found {len(source_files)}"

        for source_file in source_files:
            config = _parse_front_matter(source_file)
            assert config["type"] == "domain-model-source", f"{source_file.name}"
            assert "maps_to" in config, f"{source_file.name} missing maps_to"
            assert "from" in config, f"{source_file.name} missing from"
            assert "aliases" in config or "maps_to" in config, f"{source_file.name}"

    def test_view_file_has_required_keys(self, fixtures_dir):
        """View files should have view, view_type."""
        config = _parse_front_matter(
            fixtures_dir / "models/test_model/views/view_entity_summary.md"
        )
        assert config["type"] == "domain-model-view"
        assert "view" in config
        assert "view_type" in config
        assert config["view_type"] in ("derived", "rollup")

    def test_reference_file_not_a_model(self, fixtures_dir):
        """Reference files should have type: reference and no model: key."""
        config = _parse_front_matter(fixtures_dir / "_model_guides_/test_guide.md")
        assert config["type"] == "reference"
        assert "model" not in config


# ===========================================================================
# Phase 1: Core loader — multi-file discovery (tests added when loader exists)
# ===========================================================================

class TestPhase1CoreLoader:
    """Tests for DomainConfigLoaderV4 multi-file discovery."""

    @pytest.fixture
    def loader(self, fixtures_dir):
        """Create V4 loader pointed at test fixtures."""
        try:
            from de_funk.config.domain import DomainConfigLoaderV4
            return DomainConfigLoaderV4(fixtures_dir)
        except ImportError:
            pytest.skip("Phase 1 not yet implemented")

    def test_build_index_discovers_all_types(self, loader):
        """Index should categorize files by type."""
        index = loader._type_index
        assert "domain-base" in index
        assert "domain-model" in index
        assert "domain-model-table" in index
        assert "domain-model-source" in index
        assert "domain-model-view" in index
        assert "reference" in index

    def test_reference_files_not_in_models(self, loader):
        """Reference files should be indexed but not listed as models."""
        models = loader.list_models()
        for m in models:
            config = loader.load_model_config(m)
            assert config.get("type") != "reference"

    def test_load_model_assembles_tables(self, loader):
        """Loading test_model should auto-discover tables/*.md."""
        config = loader.load_model_config("test_model")
        assert "tables" in config
        assert "dim_entity" in config["tables"]
        assert "fact_events" in config["tables"]

    def test_load_model_assembles_sources(self, loader):
        """Loading test_model should auto-discover sources/**/*.md."""
        config = loader.load_model_config("test_model")
        assert "sources" in config
        source_names = [s.get("source") for s in config["sources"].values()]
        assert "events" in source_names
        assert "entities" in source_names

    def test_load_model_assembles_views(self, loader):
        """Loading test_model should auto-discover views/*.md."""
        config = loader.load_model_config("test_model")
        assert "views" in config
        assert "view_entity_summary" in config["views"]

    def test_extends_on_table_file(self, loader):
        """Table with extends: should inherit base schema."""
        config = loader.load_model_config("test_model")
        dim_entity = config["tables"]["dim_entity"]
        # Should have inherited schema from _base.simple.base_template._dim_entity
        assert "schema" in dim_entity
        # Should have entity_id from base
        col_names = [col[0] for col in dim_entity["schema"]]
        assert "entity_id" in col_names

    def test_extends_dot_notation(self, loader):
        """Dotted extends references should resolve correctly."""
        config = loader.load_model_config("test_model")
        # The model extends _base.simple.base_template
        assert "canonical_fields" in config or "tables" in config

    def test_deep_merge_preserves_child_overrides(self, loader):
        """Child config values should override parent values."""
        config = loader.load_model_config("test_model")
        # Model should have its own version, not parent's
        assert config.get("model") == "test_model"

    def test_model_metadata_preserved(self, loader):
        """Model metadata should survive assembly."""
        config = loader.load_model_config("test_model")
        assert config.get("metadata", {}).get("domain") == "test"
        assert config.get("status") == "active"

    def test_list_models_returns_domain_models_only(self, loader):
        """list_models() should return domain-model types only."""
        models = loader.list_models()
        assert "test_model" in models
        # Base templates should NOT appear
        assert "simple_entity" not in models

    def test_get_dependencies(self, loader):
        """Dependencies should be readable."""
        deps = loader.get_dependencies("test_model")
        assert "temporal" in deps


# ===========================================================================
# Phase 2: Schema — canonical_fields, additional_schema, derivations, subsets
# ===========================================================================

class TestPhase2Schema:
    """Tests for schema processing mechanisms."""

    @pytest.fixture
    def loader(self, fixtures_dir):
        from de_funk.config.domain import DomainConfigLoaderV4
        return DomainConfigLoaderV4(fixtures_dir)

    def test_canonical_fields_to_schema(self):
        """canonical_fields keyword format converts to positional schema format."""
        from de_funk.config.domain.schema import canonical_fields_to_schema

        canonical = [
            ["field_a", "string", {"nullable": True, "description": "Test field A"}],
            ["field_b", "integer", {"nullable": False, "description": "Test field B"}],
        ]
        schema = canonical_fields_to_schema(canonical)
        assert len(schema) == 2
        assert schema[0] == ["field_a", "string", True, "Test field A"]
        assert schema[1] == ["field_b", "integer", False, "Test field B"]

    def test_additional_schema_appended(self, loader):
        """additional_schema columns should be appended to inherited schema."""
        config = loader.load_model_config("test_model")
        dim_entity = config["tables"]["dim_entity"]
        col_names = [col[0] for col in dim_entity["schema"]]
        # region_code and priority from additional_schema
        assert "region_code" in col_names
        assert "priority" in col_names

    def test_additional_schema_after_inherited(self, loader):
        """additional_schema columns appear after inherited base columns."""
        config = loader.load_model_config("test_model")
        dim_entity = config["tables"]["dim_entity"]
        col_names = [col[0] for col in dim_entity["schema"]]
        # Base has entity_id, entity_name, entity_type, created_date
        # additional_schema has region_code, priority — they should come after
        assert col_names.index("entity_id") < col_names.index("region_code")
        assert col_names.index("entity_name") < col_names.index("priority")

    def test_derivations_override_derived(self, loader):
        """derivations: {col: "expr"} should update matching column's derived."""
        config = loader.load_model_config("test_model")
        dim_entity = config["tables"]["dim_entity"]
        # Find entity_id column — should have derivation "ABS(HASH(name))" from dim_entity.md
        found = False
        for col in dim_entity["schema"]:
            if col[0] == "entity_id":
                options = col[4] if len(col) > 4 else {}
                assert options.get("derived") == "ABS(HASH(name))"
                found = True
                break
        assert found, "entity_id column not found in dim_entity schema"

    def test_derivations_missing_column_ignored(self):
        """Derivation for nonexistent column is a safe no-op."""
        from de_funk.config.domain.schema import apply_derivations

        schema = [["col_a", "string", True, "desc"]]
        result = apply_derivations(schema, {"nonexistent_col": "EXPR()"})
        assert len(result) == 1
        assert result[0][0] == "col_a"

    def test_subset_absorption_discovers_children(self):
        """Loader should find subset children by subset_of reference."""
        base_config = _parse_front_matter(
            FIXTURES_DIR / "_base/simple/base_template.md"
        )
        assert "subsets" in base_config
        assert base_config["subsets"]["target_table"] == "_dim_entity"

    def test_subset_absorption_adds_nullable_columns(self, loader):
        """Absorbed subset columns should be nullable with {subset: VALUE}."""
        config = loader.load_base("_base.simple.base_template", with_subsets=True)
        dim_entity_schema = config["tables"]["_dim_entity"]["schema"]
        col_names = [col[0] for col in dim_entity_schema]
        # field_a1, field_a2 from subset_a and field_b1, field_b2, field_b3 from subset_b
        assert "field_a1" in col_names
        assert "field_a2" in col_names
        assert "field_b1" in col_names

    def test_subset_columns_have_metadata(self, loader):
        """Absorbed subset columns should have {subset: VALUE} metadata."""
        config = loader.load_base("_base.simple.base_template", with_subsets=True)
        dim_entity_schema = config["tables"]["_dim_entity"]["schema"]

        for col in dim_entity_schema:
            if col[0] == "field_a1":
                assert len(col) >= 5
                assert isinstance(col[4], dict)
                assert col[4].get("subset") == "TYPE_A"
                break
        else:
            pytest.fail("field_a1 not found in absorbed schema")

    def test_subset_absorption_merges_measures(self, loader):
        """Child measures should be absorbed into parent target table."""
        config = loader.load_base("_base.simple.base_template", with_subsets=True)
        dim_entity_measures = config["tables"]["_dim_entity"]["measures"]
        measure_names = [m[0] for m in dim_entity_measures if isinstance(m, list)]
        # avg_field_a2 from subset_a
        assert "avg_field_a2" in measure_names

    def test_subset_columns_are_nullable(self, loader):
        """All absorbed subset columns should be forced nullable."""
        config = loader.load_base("_base.simple.base_template", with_subsets=True)
        dim_entity_schema = config["tables"]["_dim_entity"]["schema"]

        for col in dim_entity_schema:
            if col[0] in ("field_a1", "field_a2", "field_b1", "field_b2", "field_b3"):
                assert col[2] is True, f"{col[0]} should be nullable but is {col[2]}"


# ===========================================================================
# Phase 3: Sources (placeholder — tests added with implementation)
# ===========================================================================

class TestPhase3Sources:
    """Tests for source file processing."""

    def test_aliases_to_select_list(self):
        """Alias pairs should convert to SQL SELECT expressions."""
        from de_funk.config.domain.sources import build_select_expressions

        aliases = [
            ["entity_id", "ABS(HASH(name))"],
            ["entity_name", "name"],
            ["created_date", "create_dt"],
        ]
        select_list = build_select_expressions(aliases)
        assert "ABS(HASH(name)) AS entity_id" in select_list
        assert "name AS entity_name" in select_list
        assert "create_dt AS created_date" in select_list

    def test_domain_source_injected(self):
        """domain_source literal should be added to SELECT."""
        from de_funk.config.domain.sources import build_select_expressions

        aliases = [["entity_name", "name"]]
        domain_source = "'test_provider'"
        select_list = build_select_expressions(aliases, domain_source=domain_source)
        assert "'test_provider' AS domain_source" in select_list

    def test_entry_type_injected(self):
        """entry_type discriminator should be added to SELECT."""
        from de_funk.config.domain.sources import build_select_expressions

        aliases = [["entity_name", "name"]]
        select_list = build_select_expressions(aliases, entry_type="VENDOR_PAYMENT")
        assert "'VENDOR_PAYMENT' AS entry_type" in select_list

    def test_event_type_injected(self):
        """event_type discriminator should be added to SELECT."""
        from de_funk.config.domain.sources import build_select_expressions

        aliases = [["entity_name", "name"]]
        select_list = build_select_expressions(aliases, event_type="APPROPRIATION")
        assert "'APPROPRIATION' AS event_type" in select_list

    def test_multi_source_grouped(self):
        """Two sources with same maps_to should be grouped."""
        from de_funk.config.domain.sources import group_sources_by_target

        sources = {
            "source_a": {"maps_to": "fact_events", "from": "bronze.a"},
            "source_b": {"maps_to": "fact_events", "from": "bronze.b"},
            "source_c": {"maps_to": "dim_entity", "from": "bronze.c"},
        }
        grouped = group_sources_by_target(sources)
        assert len(grouped["fact_events"]) == 2
        assert len(grouped["dim_entity"]) == 1

    def test_unpivot_plan_generated(self):
        """unpivot config should produce correct column mapping."""
        from de_funk.config.domain.sources import build_unpivot_plan

        source_config = {
            "transform": "unpivot",
            "unpivot_aliases": [
                ["totalRevenue", "TOTAL_REVENUE"],
                ["costOfRevenue", "COST_OF_REVENUE"],
                ["grossProfit", "GROSS_PROFIT"],
            ],
        }
        plan = build_unpivot_plan(source_config)
        assert plan["transform"] == "unpivot"
        assert len(plan["mappings"]) == 3
        assert ("totalRevenue", "TOTAL_REVENUE") in plan["mappings"]
        assert "totalRevenue" in plan["source_columns"]
        assert "TOTAL_REVENUE" in plan["key_values"]

    def test_unpivot_plan_empty_for_non_unpivot(self):
        """Non-unpivot source should return empty plan."""
        from de_funk.config.domain.sources import build_unpivot_plan

        source_config = {"from": "bronze.some_table"}
        plan = build_unpivot_plan(source_config)
        assert plan == {}

    def test_process_source_config(self):
        """process_source_config should enrich config with select expressions."""
        from de_funk.config.domain.sources import process_source_config

        source = {
            "aliases": [["col_a", "source_col_a"], ["col_b", "source_col_b"]],
            "domain_source": "'test'",
            "maps_to": "fact_test",
            "from": "bronze.test",
        }
        result = process_source_config(source)
        assert "_select_expressions" in result
        assert "source_col_a AS col_a" in result["_select_expressions"]
        assert "'test' AS domain_source" in result["_select_expressions"]

    def test_loader_discovers_sources_with_aliases(self):
        """Loader should discover sources with their alias configurations."""
        from de_funk.config.domain import DomainConfigLoaderV4

        loader = DomainConfigLoaderV4(FIXTURES_DIR)
        config = loader.load_model_config("test_model")
        sources = config.get("sources", {})
        assert len(sources) >= 2

        # Check events source has aliases
        events_source = sources.get("events", {})
        assert "aliases" in events_source
        assert events_source.get("maps_to") == "fact_events"


# ===========================================================================
# Phases 4-8: Placeholder test classes (tests added with each phase)
# ===========================================================================

class TestPhase4Build:
    """Tests for phased build, enrich, generated, seed."""

    def test_placeholder(self):
        pytest.skip("Phase 4 not yet implemented")


class TestPhase5Views:
    """Tests for derived and rollup view materialization."""

    def test_placeholder(self):
        pytest.skip("Phase 5 not yet implemented")


class TestPhase6Federation:
    """Tests for cross-model union tables."""

    def test_placeholder(self):
        pytest.skip("Phase 6 not yet implemented")


class TestPhase7Graph:
    """Tests for auto_edges, optional edges, paths."""

    def test_placeholder(self):
        pytest.skip("Phase 7 not yet implemented")


class TestPhase8Migration:
    """Tests for domains_testing → domains migration."""

    def test_placeholder(self):
        pytest.skip("Phase 8 not yet implemented")
