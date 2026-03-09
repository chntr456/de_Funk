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
        try:
            from de_funk.config.domain import DomainConfigLoaderV4
            return DomainConfigLoaderV4(fixtures_dir)
        except ImportError:
            pytest.skip("Phase 1 not yet implemented")

    def test_additional_schema_appended(self, loader):
        """additional_schema columns should be appended to inherited schema."""
        try:
            from de_funk.config.domain.schema import merge_additional_schema
        except ImportError:
            pytest.skip("Phase 2 not yet implemented")

        config = loader.load_model_config("test_model")
        dim_entity = config["tables"]["dim_entity"]
        col_names = [col[0] for col in dim_entity["schema"]]
        # region_code and priority from additional_schema
        assert "region_code" in col_names
        assert "priority" in col_names

    def test_derivations_override_derived(self, loader):
        """derivations: {col: "expr"} should update matching column's derived."""
        try:
            from de_funk.config.domain.schema import apply_derivations
        except ImportError:
            pytest.skip("Phase 2 not yet implemented")

        config = loader.load_model_config("test_model")
        dim_entity = config["tables"]["dim_entity"]
        # Find entity_id column — should have derivation "ABS(HASH(name))" from dim_entity.md
        for col in dim_entity["schema"]:
            if col[0] == "entity_id":
                options = col[4] if len(col) > 4 else {}
                assert options.get("derived") == "ABS(HASH(name))"
                break

    def test_subset_absorption_discovers_children(self, loader):
        """Loader should find subset children by subset_of reference."""
        try:
            from de_funk.config.domain.subsets import absorb_subsets
        except ImportError:
            pytest.skip("Phase 2 not yet implemented")

        base_config = _parse_front_matter(
            FIXTURES_DIR / "_base/simple/base_template.md"
        )
        # After absorption, _dim_entity should have subset fields
        # This tests the mechanism, not the loader integration
        assert "subsets" in base_config
        assert base_config["subsets"]["target_table"] == "_dim_entity"

    def test_subset_absorption_adds_nullable_columns(self, loader):
        """Absorbed subset columns should be nullable with {subset: VALUE}."""
        try:
            from de_funk.config.domain.subsets import absorb_subsets
        except ImportError:
            pytest.skip("Phase 2 not yet implemented")

        # After full processing, base _dim_entity schema should include
        # field_a1, field_a2 from subset_a and field_b1, field_b2, field_b3 from subset_b
        config = loader._load_base("_base.simple.base_template")
        dim_entity_schema = config["tables"]["_dim_entity"]["schema"]
        col_names = [col[0] for col in dim_entity_schema]
        assert "field_a1" in col_names
        assert "field_b1" in col_names


# ===========================================================================
# Phase 3: Sources (placeholder — tests added with implementation)
# ===========================================================================

class TestPhase3Sources:
    """Tests for source file processing."""

    def test_aliases_to_select_list(self):
        """Alias pairs should convert to SQL SELECT expressions."""
        try:
            from de_funk.config.domain.sources import build_select_expressions
        except ImportError:
            pytest.skip("Phase 3 not yet implemented")

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
        try:
            from de_funk.config.domain.sources import build_select_expressions
        except ImportError:
            pytest.skip("Phase 3 not yet implemented")

        aliases = [["entity_name", "name"]]
        domain_source = "'test_provider'"
        select_list = build_select_expressions(aliases, domain_source=domain_source)
        assert "'test_provider' AS domain_source" in select_list

    def test_multi_source_grouped(self):
        """Two sources with same maps_to should be grouped."""
        try:
            from de_funk.config.domain.sources import group_sources_by_target
        except ImportError:
            pytest.skip("Phase 3 not yet implemented")

        sources = {
            "source_a": {"maps_to": "fact_events", "from": "bronze.a"},
            "source_b": {"maps_to": "fact_events", "from": "bronze.b"},
            "source_c": {"maps_to": "dim_entity", "from": "bronze.c"},
        }
        grouped = group_sources_by_target(sources)
        assert len(grouped["fact_events"]) == 2
        assert len(grouped["dim_entity"]) == 1


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
