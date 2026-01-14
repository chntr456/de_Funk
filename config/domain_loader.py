"""
Unified model configuration loader with markdown front matter parsing.

This module provides ModelConfigLoader for loading model configurations
from markdown files with YAML front matter. This REPLACES the legacy
YAML-only loader in config/model_loader.py.

The domains/ directory structure:
    domains/
    ├── _schema/           # Schema templates (reusable)
    ├── _base/             # Base templates for inheritance
    ├── foundation/        # Foundation models (temporal, geospatial)
    ├── city/              # City-level domains
    │   └── chicago/       # Chicago-specific models
    ├── county/            # County-level domains
    │   └── cook_county/   # Cook County-specific models
    ├── corporate/         # Corporate entities
    └── securities/        # Securities models

Usage:
    from config.domain_loader import ModelConfigLoader

    loader = ModelConfigLoader(repo_root / "domains")
    config = loader.load_model_config("chicago_public_safety")
"""

import yaml
import re
import importlib
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class ModelConfigLoader:
    """
    Unified model configuration loader (drop-in replacement for legacy loader).

    Loads model configurations from markdown files with YAML front matter.
    This replaces the legacy YAML-only ModelConfigLoader in config/model_loader.py.

    Features:
    - Parses YAML front matter from .md files
    - Inheritance via 'extends' and 'schema_template' keywords
    - Deep merging of configurations
    - Python measures module discovery
    - Caching for performance
    - Drop-in compatible with legacy ModelConfigLoader API

    Usage:
        loader = ModelConfigLoader(Path("domains"))
        config = loader.load_model_config("chicago_public_safety")

        # Or load by path
        config = loader.load_from_path("city/chicago/public_safety.md")
    """

    def __init__(self, domains_dir: Path):
        """
        Initialize loader.

        Args:
            domains_dir: Path to domains directory (e.g., repo_root/domains)
        """
        self.domains_dir = Path(domains_dir)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._path_to_model: Dict[str, str] = {}  # Maps relative paths to model names
        self._model_to_path: Dict[str, str] = {}  # Maps model names to relative paths

        # Build index on initialization
        self._build_index()

    def _build_index(self):
        """Build index of all domain markdown files."""
        if not self.domains_dir.exists():
            logger.warning(f"Domains directory not found: {self.domains_dir}")
            return

        for md_file in self.domains_dir.rglob("*.md"):
            # Skip README files and templates
            if md_file.name.lower() in ['readme.md', 'proposal.md']:
                continue

            rel_path = md_file.relative_to(self.domains_dir)

            # Try to extract model name from front matter
            try:
                config = self._parse_front_matter(md_file)
                if config and 'model' in config:
                    model_name = config['model']
                    self._path_to_model[str(rel_path)] = model_name
                    self._model_to_path[model_name] = str(rel_path)
            except Exception as e:
                logger.debug(f"Could not parse {rel_path}: {e}")

    def _parse_front_matter(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse YAML front matter from markdown file.

        Args:
            file_path: Path to markdown file

        Returns:
            Parsed YAML front matter as dict
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return {}

        # Extract YAML front matter between --- delimiters
        pattern = r'^---\s*\n(.*?)\n---'
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            logger.debug(f"No front matter found in {file_path}")
            return {}

        yaml_content = match.group(1)

        try:
            config = yaml.safe_load(yaml_content)
            return config if config else {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML in {file_path}: {e}")
            return {}

    def load_model_config(self, model_name: str) -> Dict[str, Any]:
        """
        Load complete model configuration by model name.

        This is the primary API method (compatible with legacy ModelConfigLoader).

        Args:
            model_name: Name of the model (e.g., 'chicago_public_safety', 'stocks')

        Returns:
            Merged configuration dictionary
        """
        if model_name in self._cache:
            return self._cache[model_name]

        # Find the file path for this model
        if model_name not in self._model_to_path:
            # Try to find by scanning (in case index is stale)
            self._build_index()

        if model_name not in self._model_to_path:
            raise FileNotFoundError(f"Domain model '{model_name}' not found in {self.domains_dir}")

        rel_path = self._model_to_path[model_name]
        file_path = self.domains_dir / rel_path

        return self._load_from_file(file_path, model_name)

    def load_from_path(self, rel_path: str) -> Dict[str, Any]:
        """
        Load domain configuration by relative path.

        Args:
            rel_path: Relative path from domains dir (e.g., 'city/chicago/public_safety.md')

        Returns:
            Configuration dictionary
        """
        file_path = self.domains_dir / rel_path

        if not file_path.exists():
            raise FileNotFoundError(f"Domain file not found: {file_path}")

        config = self._parse_front_matter(file_path)
        model_name = config.get('model', file_path.stem)

        return self._load_from_file(file_path, model_name)

    def _load_from_file(self, file_path: Path, model_name: str) -> Dict[str, Any]:
        """
        Load and process configuration from a file.

        Args:
            file_path: Path to the markdown file
            model_name: Model name for caching

        Returns:
            Processed configuration dictionary
        """
        if model_name in self._cache:
            return self._cache[model_name]

        # Parse front matter
        config = self._parse_front_matter(file_path)

        if not config:
            raise ValueError(f"No valid configuration found in {file_path}")

        # Store file path for reference
        config['_source_file'] = str(file_path.relative_to(self.domains_dir))

        # Resolve schema_template if present
        if 'schema_template' in config:
            template_config = self._load_template(config['schema_template'])
            config = self._deep_merge(template_config, config)

        # Resolve extends if present (top-level)
        if 'extends' in config:
            parent_config = self._load_extends(config['extends'])
            config = self._deep_merge(parent_config, config)

        # Resolve nested extends in schema, graph, measures
        config = self._resolve_nested_extends(config)

        # Ensure model name is set
        if 'model' not in config:
            config['model'] = model_name

        # Derive python_module from path (convention over configuration)
        # domains/city/chicago/public_safety.md → models/domains/city/chicago/public_safety/
        rel_path = file_path.relative_to(self.domains_dir)
        path_without_ext = str(rel_path).replace('.md', '')
        config['_python_module'] = f"models/domains/{path_without_ext}"

        # Cache and return
        self._cache[model_name] = config
        return config

    def _load_template(self, template_path: str) -> Dict[str, Any]:
        """
        Load a schema template.

        Args:
            template_path: Path like '_schema/crime.md'

        Returns:
            Template configuration
        """
        # Normalize path
        if not template_path.endswith('.md'):
            template_path += '.md'

        file_path = self.domains_dir / template_path

        if not file_path.exists():
            logger.warning(f"Template not found: {file_path}")
            return {}

        return self._parse_front_matter(file_path)

    def _load_extends(self, extends_path: str) -> Dict[str, Any]:
        """
        Load configuration from extends path.

        Args:
            extends_path: Path like '_base/securities/securities.md' or model name

        Returns:
            Extended configuration
        """
        # Check if it's a path or a model name
        if '/' in extends_path or extends_path.endswith('.md'):
            # It's a path
            if not extends_path.endswith('.md'):
                extends_path += '.md'
            file_path = self.domains_dir / extends_path
        else:
            # It's a model name - look it up
            if extends_path in self._model_to_path:
                file_path = self.domains_dir / self._model_to_path[extends_path]
            else:
                logger.warning(f"Could not resolve extends: {extends_path}")
                return {}

        if not file_path.exists():
            logger.warning(f"Extends file not found: {file_path}")
            return {}

        return self._parse_front_matter(file_path)

    def _resolve_nested_extends(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve extends directives in nested structures.

        Handles extends in:
        - schema.dimensions.{dim_name}.extends
        - schema.facts.{fact_name}.extends
        - graph.nodes.{node_name}.extends
        - etc.
        """
        # Sections that can have nested extends
        sections_with_extends = [
            ('schema', 'dimensions'),
            ('schema', 'facts'),
            ('graph', 'nodes'),
            ('graph', 'edges'),
            ('measures', 'simple'),
            ('measures', 'computed'),
        ]

        for section, subsection in sections_with_extends:
            if section in config and isinstance(config[section], dict):
                if subsection in config[section] and isinstance(config[section][subsection], dict):
                    for key, value in config[section][subsection].items():
                        if isinstance(value, dict) and 'extends' in value:
                            parent = self._resolve_extends_reference(value['extends'])
                            value_without_extends = {k: v for k, v in value.items() if k != 'extends'}
                            config[section][subsection][key] = self._deep_merge(parent, value_without_extends)

        return config

    def _resolve_extends_reference(self, extends_ref: str) -> Dict[str, Any]:
        """
        Resolve an extends reference that may point to a specific section.

        Args:
            extends_ref: Reference like '_schema/crime.canonical_schema' or '_base/securities._dim_security'

        Returns:
            Resolved configuration section
        """
        parts = extends_ref.split('.')

        if len(parts) == 1:
            # Just a file reference
            return self._load_extends(parts[0])

        # First part is file/path, rest is navigation path
        file_ref = parts[0]
        nav_path = parts[1:]

        # Load the base file
        base_config = self._load_extends(file_ref)

        # Navigate to the specific section
        current = base_config
        for nav in nav_path:
            if isinstance(current, dict) and nav in current:
                current = current[nav]
            else:
                logger.warning(f"Could not navigate to {nav} in {extends_ref}")
                return {}

        return current if isinstance(current, dict) else {}

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """
        Deep merge two dictionaries.
        Override values take precedence.

        Special handling:
        - Lists are replaced, not merged
        - Dicts are recursively merged
        - Keys starting with '_' in override are preserved
        """
        result = base.copy()

        for key, value in override.items():
            if key in result:
                if isinstance(result[key], dict) and isinstance(value, dict):
                    # Recursively merge dicts
                    result[key] = self._deep_merge(result[key], value)
                else:
                    # Replace (including lists)
                    result[key] = value
            else:
                result[key] = value

        return result

    def list_domains(self, domain_type: str = None) -> List[str]:
        """
        List all available domain models.

        Args:
            domain_type: Optional filter by type (e.g., 'domain-model', 'schema-template')

        Returns:
            List of model names
        """
        models = []

        for model_name, rel_path in self._model_to_path.items():
            if domain_type:
                file_path = self.domains_dir / rel_path
                config = self._parse_front_matter(file_path)
                if config.get('type') == domain_type:
                    models.append(model_name)
            else:
                models.append(model_name)

        return sorted(models)

    def list_by_category(self) -> Dict[str, List[str]]:
        """
        List domains organized by category.

        Returns:
            Dict mapping category to list of model names
        """
        categories: Dict[str, List[str]] = {}

        for model_name, rel_path in self._model_to_path.items():
            # Extract category from path (first directory)
            parts = Path(rel_path).parts
            if len(parts) > 1:
                category = parts[0]
            else:
                category = 'root'

            if category not in categories:
                categories[category] = []
            categories[category].append(model_name)

        return {k: sorted(v) for k, v in sorted(categories.items())}

    def get_dependencies(self, model_name: str) -> List[str]:
        """
        Get dependencies for a model.

        Args:
            model_name: Model name

        Returns:
            List of dependency model names
        """
        config = self.load_model_config(model_name)
        return config.get('depends_on', [])

    def list_models(self) -> List[str]:
        """
        List all available models (compatible with legacy API).

        Returns:
            List of model names
        """
        return self.list_domains(domain_type='domain-model')

    def get_build_order(self, models: List[str] = None) -> List[str]:
        """
        Get topologically sorted build order.

        Args:
            models: Optional list of models to include (default: all)

        Returns:
            Models in build order (dependencies first)
        """
        if models is None:
            models = self.list_domains(domain_type='domain-model')

        # Build dependency graph
        graph: Dict[str, List[str]] = {}
        for model in models:
            try:
                deps = self.get_dependencies(model)
                # Only include dependencies that are in our model list
                graph[model] = [d for d in deps if d in models]
            except Exception as e:
                logger.warning(f"Could not get dependencies for {model}: {e}")
                graph[model] = []

        # Topological sort (Kahn's algorithm)
        in_degree = {m: 0 for m in models}
        for model, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[model] += 1

        queue = [m for m in models if in_degree[m] == 0]
        result = []

        while queue:
            model = queue.pop(0)
            result.append(model)

            for other, deps in graph.items():
                if model in deps:
                    in_degree[other] -= 1
                    if in_degree[other] == 0 and other not in result:
                        queue.append(other)

        if len(result) != len(models):
            missing = set(models) - set(result)
            logger.warning(f"Circular dependencies detected. Missing: {missing}")
            result.extend(missing)

        return result

    def load_python_measures(self, model_name: str, model_instance=None) -> Optional[Any]:
        """
        Load Python measures module for a model.

        Args:
            model_name: Model name
            model_instance: Model instance to pass to measures class

        Returns:
            Measures class instance or None
        """
        config = self.load_model_config(model_name)

        # Use derived _python_module (convention-based)
        python_module = config.get('_python_module')
        if not python_module:
            return None

        # Convert path to module: 'models/domains/city/chicago/public_safety' -> module path
        module_path = python_module.rstrip('/').replace('/', '.')
        measures_module = f"{module_path}.measures"

        try:
            module = importlib.import_module(measures_module)

            # Look for {ModelName}Measures class
            # Convert model_name to class name: chicago_public_safety -> ChicagoPublicSafetyMeasures
            class_name = ''.join(word.title() for word in model_name.split('_')) + 'Measures'

            if hasattr(module, class_name):
                measures_class = getattr(module, class_name)
                if model_instance:
                    return measures_class(model_instance)
                else:
                    return measures_class
            else:
                logger.debug(f"Measures class '{class_name}' not found in {measures_module}")
        except ImportError as e:
            logger.debug(f"Could not import measures from {measures_module}: {e}")

        return None

    def clear_cache(self):
        """Clear the configuration cache."""
        self._cache.clear()

    def refresh_index(self):
        """Refresh the domain index."""
        self._path_to_model.clear()
        self._model_to_path.clear()
        self._build_index()
