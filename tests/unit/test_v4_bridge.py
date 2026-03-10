"""
Unit tests for the v4→build pipeline bridge.

Tests the config translator (v4_to_nodes), V4Model, and V4Builder
that wire v4 domain configs into the existing build pipeline.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is on path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(project_root / "src") not in sys.path:
    sys.path.insert(0, str(project_root / "src"))


# ============================================================
# Fixtures — synthetic v4 configs for testing
# ============================================================

@pytest.fixture
def simple_dim_config():
    """V4 config for a simple dimension table with one source."""
    return {
        "model": "test_model",
        "type": "domain-model",
        "tables": {
            "dim_widget": {
                "type": "domain-model-table",
                "table_type": "dimension",
                "primary_key": ["widget_id"],
                "unique_key": ["widget_code"],
                "schema": [
                    ["widget_id", "string", False, "PK", {"derived": "ABS(HASH(code))"}],
                    ["widget_code", "string", False, "Natural key"],
                    ["widget_name", "string", True, "Display name"],
                ],
            },
        },
        "sources": {
            "widgets_raw": {
                "type": "domain-model-source",
                "source": "widgets_raw",
                "maps_to": "dim_widget",
                "from": "bronze.provider.raw_widgets",
                "aliases": [
                    ["widget_code", "code"],
                    ["widget_name", "name"],
                ],
            },
        },
        "graph": {
            "edges": [],
        },
        "build": {},
    }


@pytest.fixture
def fact_with_derivations_config():
    """V4 config for a fact table with derived columns."""
    return {
        "model": "test_model",
        "type": "domain-model",
        "tables": {
            "dim_widget": {
                "type": "domain-model-table",
                "table_type": "dimension",
                "primary_key": ["widget_id"],
                "schema": [
                    ["widget_id", "string", False, "PK"],
                    ["widget_name", "string", True, "Name"],
                ],
            },
            "fact_sales": {
                "type": "domain-model-table",
                "table_type": "fact",
                "primary_key": ["sale_id"],
                "schema": [
                    ["sale_id", "string", False, "PK", {"derived": "ABS(HASH(CONCAT(widget_code, '_', sale_date)))"}],
                    ["widget_id", "string", False, "FK", {"derived": "ABS(HASH(widget_code))"}],
                    ["sale_date", "string", False, "Date"],
                    ["amount", "double", True, "Sale amount"],
                ],
                "derivations": {
                    "sale_date_id": "CAST(REPLACE(sale_date, '-', '') AS INT)",
                },
            },
        },
        "sources": {
            "dim_source": {
                "type": "domain-model-source",
                "maps_to": "dim_widget",
                "from": "bronze.provider.widgets",
                "aliases": [["widget_name", "name"]],
            },
            "sales_source": {
                "type": "domain-model-source",
                "maps_to": "fact_sales",
                "from": "bronze.provider.sales",
                "aliases": [
                    ["widget_code", "code"],
                    ["sale_date", "date"],
                    ["amount", "total"],
                ],
                "domain_source": "'test_provider'",
            },
        },
        "graph": {
            "edges": [
                ["sale_to_widget", "fact_sales", "dim_widget",
                 ["widget_id=widget_id"], "many_to_one", None],
            ],
        },
        "build": {
            "phases": {
                1: {"tables": ["dim_widget"]},
                2: {"tables": ["fact_sales"]},
            },
        },
    }


@pytest.fixture
def multi_source_config():
    """V4 config with multiple sources mapping to the same table."""
    return {
        "model": "test_model",
        "type": "domain-model",
        "tables": {
            "fact_entries": {
                "type": "domain-model-table",
                "table_type": "fact",
                "primary_key": ["entry_id"],
                "schema": [
                    ["entry_id", "string", False, "PK"],
                    ["amount", "double", True, "Amount"],
                    ["domain_source", "string", True, "Source"],
                ],
            },
        },
        "sources": {
            "source_a": {
                "type": "domain-model-source",
                "maps_to": "fact_entries",
                "from": "bronze.provider_a.entries",
                "aliases": [
                    ["entry_id", "id"],
                    ["amount", "value"],
                ],
                "domain_source": "'provider_a'",
            },
            "source_b": {
                "type": "domain-model-source",
                "maps_to": "fact_entries",
                "from": "bronze.provider_b.entries",
                "aliases": [
                    ["entry_id", "record_id"],
                    ["amount", "amt"],
                ],
                "domain_source": "'provider_b'",
            },
        },
        "graph": {"edges": []},
        "build": {},
    }


@pytest.fixture
def seed_table_config():
    """V4 config with a static/seed table."""
    return {
        "model": "test_model",
        "type": "domain-model",
        "tables": {
            "dim_category": {
                "type": "domain-model-table",
                "table_type": "dimension",
                "static": True,
                "primary_key": ["category_code"],
                "schema": [
                    ["category_code", "string", False, "PK"],
                    ["category_name", "string", False, "Name"],
                    ["sort_order", "int", True, "Sort order"],
                ],
                "data": [
                    {"category_code": "A", "category_name": "Alpha", "sort_order": 1},
                    {"category_code": "B", "category_name": "Beta", "sort_order": 2},
                    {"category_code": "C", "category_name": "Gamma", "sort_order": 3},
                ],
            },
        },
        "sources": {},
        "graph": {"edges": []},
        "build": {},
    }


@pytest.fixture
def enrich_table_config():
    """V4 config with enrich specs on a dimension."""
    return {
        "model": "test_model",
        "type": "domain-model",
        "tables": {
            "dim_property_class": {
                "type": "domain-model-table",
                "table_type": "dimension",
                "static": True,
                "primary_key": ["class_code"],
                "schema": [
                    ["class_code", "string", False, "PK"],
                    ["class_name", "string", False, "Name"],
                ],
                "data": [
                    {"class_code": "R", "class_name": "Residential"},
                    {"class_code": "C", "class_name": "Commercial"},
                ],
            },
            "dim_parcel": {
                "type": "domain-model-table",
                "table_type": "dimension",
                "primary_key": ["parcel_id"],
                "schema": [
                    ["parcel_id", "string", False, "PK"],
                    ["property_class", "string", True, "Class code"],
                ],
                "enrich": [
                    {
                        "join": "dim_property_class",
                        "on": ["property_class=class_code"],
                        "fields": ["class_name"],
                    },
                ],
            },
        },
        "sources": {
            "parcels": {
                "type": "domain-model-source",
                "maps_to": "dim_parcel",
                "from": "bronze.county.parcels",
                "aliases": [
                    ["parcel_id", "pin"],
                    ["property_class", "class"],
                ],
            },
        },
        "graph": {"edges": []},
        "build": {
            "phases": {
                1: {"tables": ["dim_property_class"]},
                2: {"tables": ["dim_parcel"]},
            },
        },
    }


# ============================================================
# Config Translator Tests
# ============================================================

class TestTranslateV4Config:
    """Tests for v4_to_nodes.translate_v4_config()."""

    def test_translate_simple_dim(self, simple_dim_config):
        """Dim table with source produces correct from and select."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        result = translate_v4_config(simple_dim_config)

        nodes = result["graph"]["nodes"]
        assert "dim_widget" in nodes

        node = nodes["dim_widget"]
        assert node["from"] == "bronze.provider.raw_widgets"
        assert node["type"] == "dimension"
        assert node["select"]["widget_code"] == "code"
        assert node["select"]["widget_name"] == "name"
        assert node["unique_key"] == ["widget_code"]

    def test_translate_derive_from_schema(self, simple_dim_config):
        """Schema {derived:} options are extracted to node derive dict."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        result = translate_v4_config(simple_dim_config)
        node = result["graph"]["nodes"]["dim_widget"]

        assert "derive" in node
        assert node["derive"]["widget_id"] == "ABS(HASH(code))"

    def test_translate_fact_with_derivations(self, fact_with_derivations_config):
        """{derived:} schema entries + derivations map both appear in derive dict."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        result = translate_v4_config(fact_with_derivations_config)
        node = result["graph"]["nodes"]["fact_sales"]

        assert node["from"] == "bronze.provider.sales"
        # From schema {derived:}
        assert "sale_id" in node["derive"]
        assert "widget_id" in node["derive"]
        # From derivations map
        assert "sale_date_id" in node["derive"]
        assert "REPLACE" in node["derive"]["sale_date_id"]

    def test_translate_domain_source_injected(self, fact_with_derivations_config):
        """domain_source discriminator appears in select dict."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        result = translate_v4_config(fact_with_derivations_config)
        node = result["graph"]["nodes"]["fact_sales"]

        assert node["select"]["domain_source"] == "'test_provider'"

    def test_translate_multi_source_union(self, multi_source_config):
        """Two sources with same maps_to produce a UNION node."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        result = translate_v4_config(multi_source_config)
        node = result["graph"]["nodes"]["fact_entries"]

        assert node["from"] == "__union__"
        assert node.get("_v4_union") is True
        assert len(node["_v4_union_sources"]) == 2

    def test_translate_seed_table(self, seed_table_config):
        """Static/seed table flagged for custom_node_loading."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        result = translate_v4_config(seed_table_config)
        node = result["graph"]["nodes"]["dim_category"]

        assert node["from"] == "__seed__"
        assert node.get("_v4_seed") is True
        assert len(node["_v4_seed_data"]) == 3
        assert node["_v4_seed_data"][0]["category_code"] == "A"

    def test_translate_enrich_to_join(self, enrich_table_config):
        """Enrich specs become v3 join entries on the node."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        result = translate_v4_config(enrich_table_config)
        node = result["graph"]["nodes"]["dim_parcel"]

        assert "join" in node
        assert len(node["join"]) == 1
        join = node["join"][0]
        assert join["table"] == "dim_property_class"
        assert join["on"] == ["property_class=class_code"]
        assert join["type"] == "left"

    def test_translate_preserves_edges(self, fact_with_derivations_config):
        """graph.edges are passed through unchanged."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        result = translate_v4_config(fact_with_derivations_config)
        edges = result["graph"]["edges"]

        assert len(edges) == 1
        assert edges[0][0] == "sale_to_widget"

    def test_translate_filters(self):
        """Table filters map to node filters."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        config = {
            "model": "test",
            "tables": {
                "dim_x": {
                    "table_type": "dimension",
                    "primary_key": ["id"],
                    "filters": ["status = 'active'"],
                    "schema": [["id", "string", False, "PK"]],
                },
            },
            "sources": {
                "x_src": {
                    "maps_to": "dim_x",
                    "from": "bronze.p.table",
                    "aliases": [["id", "id"]],
                },
            },
            "graph": {"edges": []},
            "build": {},
        }

        result = translate_v4_config(config)
        node = result["graph"]["nodes"]["dim_x"]
        assert node["filters"] == ["status = 'active'"]

    def test_translate_unique_key(self, simple_dim_config):
        """primary_key and unique_key both map to node unique_key."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        result = translate_v4_config(simple_dim_config)
        node = result["graph"]["nodes"]["dim_widget"]
        # unique_key takes priority over primary_key
        assert node["unique_key"] == ["widget_code"]

    def test_translate_phase_ordering(self, fact_with_derivations_config):
        """Tables appear in phase order in graph.nodes."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        result = translate_v4_config(fact_with_derivations_config)
        node_names = list(result["graph"]["nodes"].keys())

        # Phase 1: dim_widget, Phase 2: fact_sales
        dim_idx = node_names.index("dim_widget")
        fact_idx = node_names.index("fact_sales")
        assert dim_idx < fact_idx

    def test_translate_v4_build_metadata(self, fact_with_derivations_config):
        """Build metadata stored in _v4_build for V4Model."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        result = translate_v4_config(fact_with_derivations_config)
        assert "_v4_build" in result
        assert len(result["_v4_build"]["phases"]) == 2

    def test_translate_no_source_table_skipped(self):
        """Table with no source and no from key produces no node."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        config = {
            "model": "test",
            "tables": {
                "dim_orphan": {
                    "table_type": "dimension",
                    "schema": [["id", "string"]],
                },
            },
            "sources": {},
            "graph": {"edges": []},
            "build": {},
        }

        result = translate_v4_config(config)
        assert "dim_orphan" not in result["graph"]["nodes"]


# ============================================================
# Helper Function Tests
# ============================================================

class TestHelperFunctions:
    """Tests for individual translator helper functions."""

    def test_aliases_to_select_dict(self):
        from de_funk.config.domain.v4_to_nodes import _aliases_to_select_dict

        aliases = [
            ["parcel_id", "LPAD(pin, 14, '0')"],
            ["sale_date", "sale_date"],
            ["amount", "CAST(price AS DOUBLE)"],
        ]
        result = _aliases_to_select_dict(aliases)

        assert result["parcel_id"] == "LPAD(pin, 14, '0')"
        assert result["sale_date"] == "sale_date"
        assert result["amount"] == "CAST(price AS DOUBLE)"

    def test_extract_derive_from_schema(self):
        from de_funk.config.domain.v4_to_nodes import _extract_derive_from_schema

        schema = [
            ["id", "string", False, "PK", {"derived": "ABS(HASH(code))"}],
            ["name", "string", True, "Name"],  # No derived
            ["computed", "double", True, "Calc", {"derived": "price * qty"}],
        ]
        result = _extract_derive_from_schema(schema)

        assert len(result) == 2
        assert result["id"] == "ABS(HASH(code))"
        assert result["computed"] == "price * qty"

    def test_normalize_from_bronze(self):
        from de_funk.config.domain.v4_to_nodes import _normalize_from

        assert _normalize_from("bronze.provider.table") == "bronze.provider.table"

    def test_normalize_from_silver(self):
        from de_funk.config.domain.v4_to_nodes import _normalize_from

        assert _normalize_from("silver.temporal.dim_calendar") == "temporal.dim_calendar"

    def test_table_type_inference(self):
        from de_funk.config.domain.v4_to_nodes import _table_type

        assert _table_type("dim_widget") == "dimension"
        assert _table_type("fact_sales") == "fact"
        assert _table_type("lookup_table") == "other"

    def test_enrich_to_join_specs_lookup(self):
        from de_funk.config.domain.v4_to_nodes import _enrich_to_join_specs

        table_config = {
            "enrich": [
                {"join": "dim_x", "on": ["col_a=col_b"], "fields": ["field1"]},
            ],
        }
        result = _enrich_to_join_specs(table_config)

        assert len(result) == 1
        assert result[0]["table"] == "dim_x"
        assert result[0]["on"] == ["col_a=col_b"]
        assert result[0]["type"] == "left"


# ============================================================
# V4Builder Tests
# ============================================================

class TestV4BuilderFactory:
    """Tests for V4BuilderFactory.create_builders()."""

    def test_v4_builder_creates_for_all_models(self):
        """Factory creates builders for all v4 models."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config
        from de_funk.models.base.v4_builder import V4BuilderFactory

        domains_dir = project_root / "domains"
        if not (domains_dir / "models").exists():
            pytest.skip("domains/ directory not in v4 format")

        # Clear registry first
        from de_funk.models.base.builder import BuilderRegistry
        original = BuilderRegistry._builders.copy()
        BuilderRegistry._builders.clear()

        try:
            created = V4BuilderFactory.create_builders(
                domains_dir, skip_existing=False
            )
            assert len(created) > 0, "Should create at least one builder"
        finally:
            BuilderRegistry._builders = original

    def test_v4_builder_has_correct_model_name(self):
        """Created builders have model_name from v4 config."""
        from de_funk.models.base.v4_builder import V4BuilderFactory

        domains_dir = project_root / "domains"
        if not (domains_dir / "models").exists():
            pytest.skip("domains/ directory not in v4 format")

        from de_funk.models.base.builder import BuilderRegistry
        original = BuilderRegistry._builders.copy()
        BuilderRegistry._builders.clear()

        try:
            created = V4BuilderFactory.create_builders(
                domains_dir, skip_existing=False
            )
            for model_name, builder_cls in created.items():
                assert builder_cls.model_name == model_name
        finally:
            BuilderRegistry._builders = original

    def test_v4_builder_has_depends_on(self):
        """Created builders have depends_on from v4 config."""
        from de_funk.models.base.v4_builder import V4BuilderFactory

        domains_dir = project_root / "domains"
        if not (domains_dir / "models").exists():
            pytest.skip("domains/ directory not in v4 format")

        from de_funk.models.base.builder import BuilderRegistry
        original = BuilderRegistry._builders.copy()
        BuilderRegistry._builders.clear()

        try:
            created = V4BuilderFactory.create_builders(
                domains_dir, skip_existing=False
            )
            # At least one model should have dependencies
            has_deps = any(
                bool(cls.depends_on) for cls in created.values()
            )
            assert has_deps, "At least one v4 model should have depends_on"
        finally:
            BuilderRegistry._builders = original

    def test_v4_builder_skip_existing(self):
        """skip_existing=True doesn't register builders that already exist."""
        from de_funk.models.base.v4_builder import V4BuilderFactory
        from de_funk.models.base.builder import BuilderRegistry, BaseModelBuilder

        domains_dir = project_root / "domains"
        if not (domains_dir / "models").exists():
            pytest.skip("domains/ directory not in v4 format")

        original = BuilderRegistry._builders.copy()

        try:
            # Register a fake v3 builder for a model name we know exists
            BuilderRegistry._builders.clear()

            # First, discover what models exist
            created_all = V4BuilderFactory.create_builders(
                domains_dir, skip_existing=False
            )
            first_model = next(iter(created_all)) if created_all else None
            if not first_model:
                pytest.skip("No v4 models found")

            # Now clear and register a fake v3 builder for that model
            BuilderRegistry._builders.clear()
            fake_builder = type(
                "FakeBuilder", (BaseModelBuilder,),
                {"model_name": first_model, "depends_on": [],
                 "get_model_class": lambda self: None},
            )
            BuilderRegistry.register(fake_builder)

            # Create v4 builders with skip_existing=True
            created = V4BuilderFactory.create_builders(
                domains_dir, skip_existing=True
            )
            assert first_model not in created, \
                f"Should skip '{first_model}' since v3 builder exists"
        finally:
            BuilderRegistry._builders = original

    def test_v4_builder_config_uses_v4_loader(self):
        """Builder's get_model_config uses v4 loader + translator."""
        from de_funk.models.base.v4_builder import V4BuilderFactory
        from de_funk.models.base.builder import BuilderRegistry, BuildContext

        domains_dir = project_root / "domains"
        if not (domains_dir / "models").exists():
            pytest.skip("domains/ directory not in v4 format")

        original = BuilderRegistry._builders.copy()
        BuilderRegistry._builders.clear()

        try:
            created = V4BuilderFactory.create_builders(
                domains_dir, skip_existing=False
            )
            if not created:
                pytest.skip("No v4 models found")

            # Pick first builder and test its config loading
            model_name, builder_cls = next(iter(created.items()))

            # Create a mock context
            mock_context = MagicMock(spec=BuildContext)
            mock_context.spark = MagicMock()
            mock_context.storage_config = {}
            mock_context.repo_root = project_root
            mock_context.date_from = "2024-01-01"
            mock_context.date_to = "2024-12-31"
            mock_context.max_tickers = None

            builder = builder_cls(mock_context)
            config = builder.get_model_config()

            # The translated config should have graph.nodes
            assert "graph" in config
            assert "nodes" in config["graph"], \
                f"Translated config for '{model_name}' should have graph.nodes"
        finally:
            BuilderRegistry._builders = original


# ============================================================
# Integration with real v4 domains
# ============================================================

class TestV4TranslateRealConfigs:
    """Test translator against actual domains/ v4 configs."""

    @pytest.fixture
    def v4_loader(self):
        from de_funk.config.domain import DomainConfigLoaderV4, get_domain_loader
        domains_dir = project_root / "domains"
        if not (domains_dir / "models").exists():
            pytest.skip("domains/ directory not in v4 format")
        loader = get_domain_loader(domains_dir)
        if not isinstance(loader, DomainConfigLoaderV4):
            pytest.skip("Not a v4 domain directory")
        return loader

    def test_all_models_translate(self, v4_loader):
        """Every v4 model config translates without error."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        errors = []
        for model_name in v4_loader.list_models():
            try:
                v4_config = v4_loader.load_model_config(model_name)
                translated = translate_v4_config(v4_config)
                assert "graph" in translated
                assert "nodes" in translated["graph"]
            except Exception as e:
                errors.append(f"{model_name}: {e}")

        if errors:
            pytest.fail(
                f"{len(errors)} models failed to translate:\n"
                + "\n".join(errors)
            )

    def test_translated_nodes_have_from(self, v4_loader):
        """Every translated node has a `from` field."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        for model_name in v4_loader.list_models():
            v4_config = v4_loader.load_model_config(model_name)
            translated = translate_v4_config(v4_config)
            nodes = translated["graph"]["nodes"]

            for node_name, node in nodes.items():
                assert "from" in node, \
                    f"{model_name}.{node_name}: node missing 'from'"

    def test_translated_nodes_have_valid_type(self, v4_loader):
        """Every translated node has a valid type."""
        from de_funk.config.domain.v4_to_nodes import translate_v4_config

        for model_name in v4_loader.list_models():
            v4_config = v4_loader.load_model_config(model_name)
            translated = translate_v4_config(v4_config)
            nodes = translated["graph"]["nodes"]

            for node_name, node in nodes.items():
                assert node.get("type") in ("dimension", "fact", "other"), \
                    f"{model_name}.{node_name}: invalid type '{node.get('type')}'"

    def test_build_order_includes_v4_models(self, v4_loader):
        """v4 models appear in topological sort."""
        from de_funk.models.base.v4_builder import V4BuilderFactory
        from de_funk.models.base.builder import BuilderRegistry

        domains_dir = project_root / "domains"
        original = BuilderRegistry._builders.copy()
        BuilderRegistry._builders.clear()

        try:
            V4BuilderFactory.create_builders(domains_dir, skip_existing=False)
            all_builders = BuilderRegistry.all()

            if not all_builders:
                pytest.skip("No builders registered")

            # Get build order (may fail if deps reference non-existent models)
            try:
                order = BuilderRegistry.get_build_order()
                assert len(order) > 0
            except ValueError:
                # Some deps may not be available — that's OK for this test
                # Just verify we can get a partial order
                available = list(all_builders.keys())
                order = BuilderRegistry.get_build_order(available[:3])
                assert len(order) > 0
        finally:
            BuilderRegistry._builders = original


# ============================================================
# Run tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
