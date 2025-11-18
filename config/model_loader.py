"""
Model configuration loader with YAML inheritance and modular support.

This module provides ModelConfigLoader for loading model configurations
that are split across multiple YAML files with inheritance support.
"""

import yaml
import importlib
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ModelConfigLoader:
    """
    Loads modular model configurations with inheritance support.

    Features:
    - Modular YAMLs (schema.yaml, graph.yaml, measures.yaml separate)
    - Inheritance via 'inherits_from' and 'extends' keywords
    - Deep merging of configurations
    - Python measures module loading

    Usage:
        loader = ModelConfigLoader(Path("configs/models"))
        config = loader.load_model_config("stocks")
    """

    def __init__(self, models_dir: Path):
        """
        Initialize loader.

        Args:
            models_dir: Path to models directory (e.g., configs/models)
        """
        self.models_dir = Path(models_dir)
        self._cache = {}

    def load_model_config(self, model_name: str) -> Dict[str, Any]:
        """
        Load complete model configuration with inheritance resolution.

        Args:
            model_name: Name of the model (e.g., 'stocks')

        Returns:
            Merged configuration dictionary
        """
        if model_name in self._cache:
            return self._cache[model_name]

        model_dir = self.models_dir / model_name

        # Check if model directory exists
        if not model_dir.exists():
            # Fallback: Try loading single YAML file (backward compatibility)
            yaml_path = self.models_dir / f"{model_name}.yaml"
            if yaml_path.exists():
                logger.info(f"Loading model '{model_name}' from single YAML file (legacy)")
                return self._load_yaml(yaml_path)
            else:
                raise FileNotFoundError(f"Model '{model_name}' not found at {model_dir}")

        # Load main model.yaml
        main_config_path = model_dir / 'model.yaml'
        if main_config_path.exists():
            main_config = self._load_yaml(main_config_path)
        else:
            # If no model.yaml, create empty config
            main_config = {'model': model_name}

        # Resolve inheritance
        if 'inherits_from' in main_config:
            base_config = self._load_base_config(main_config['inherits_from'])
            merged = self._deep_merge(base_config, main_config)
        else:
            merged = main_config

        # Load component files
        if 'components' in merged:
            components = merged['components']

            # Load schema
            if 'schema' in components:
                schema_path = self.models_dir / components['schema']
                schema_config = self._load_yaml(schema_path)
                merged['schema'] = self._resolve_extends(schema_config)

            # Load graph
            if 'graph' in components:
                graph_path = self.models_dir / components['graph']
                graph_config = self._load_yaml(graph_path)
                merged['graph'] = self._resolve_extends(graph_config)

            # Load measures
            if 'measures' in components:
                if isinstance(components['measures'], dict):
                    # New format: { yaml: path, python: path }
                    if 'yaml' in components['measures']:
                        measures_yaml_path = self.models_dir / components['measures']['yaml']
                        measures_config = self._load_yaml(measures_yaml_path)
                        merged['measures'] = self._resolve_extends(measures_config)

                    # Store Python module path for later loading
                    if 'python' in components['measures']:
                        if 'measures' not in merged:
                            merged['measures'] = {}
                        merged['measures']['_python_module'] = components['measures']['python']
                else:
                    # Old format: just a path string
                    measures_path = self.models_dir / components['measures']
                    measures_config = self._load_yaml(measures_path)
                    merged['measures'] = self._resolve_extends(measures_config)
        else:
            # No components section - try loading component files by convention
            for component_name in ['schema', 'graph', 'measures']:
                component_path = model_dir / f'{component_name}.yaml'
                if component_path.exists():
                    component_config = self._load_yaml(component_path)
                    merged[component_name] = self._resolve_extends(component_config)

            # Check for Python measures
            python_measures_path = model_dir / 'measures.py'
            if python_measures_path.exists():
                if 'measures' not in merged:
                    merged['measures'] = {}
                merged['measures']['_python_module'] = f'{model_name}/measures.py'

        self._cache[model_name] = merged
        return merged

    def _load_base_config(self, base_path: str) -> Dict[str, Any]:
        """
        Load base template configuration.

        Args:
            base_path: Path like '_base.securities' or '_base/securities'

        Returns:
            Merged configuration from all base component files
        """
        base_path = base_path.replace('.', '/')
        base_dir = self.models_dir / base_path

        if not base_dir.exists():
            logger.warning(f"Base template not found: {base_dir}")
            return {}

        config = {}

        # Load all component files from base
        for component_file in ['schema.yaml', 'graph.yaml', 'measures.yaml']:
            file_path = base_dir / component_file
            if file_path.exists():
                component_name = component_file.replace('.yaml', '')
                config[component_name] = self._load_yaml(file_path)

        return config

    def _resolve_extends(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve 'extends' directives in configuration.

        Example:
          extends: _base.securities.schema
          dimensions:
            dim_stock:
              extends: _base.securities._dim_security
              columns: {...}
        """
        if not isinstance(config, dict):
            return config

        # Check for top-level extends
        if 'extends' in config:
            # Load parent config
            parent_path = config['extends']
            parent = self._load_extends_path(parent_path)

            # Remove extends key
            config_without_extends = {k: v for k, v in config.items() if k != 'extends'}

            # Deep merge
            config = self._deep_merge(parent, config_without_extends)

        # Recursively resolve extends in nested structures
        for section in ['dimensions', 'facts', 'nodes', 'edges', 'simple_measures',
                       'computed_measures', 'python_measures']:
            if section in config and isinstance(config[section], dict):
                for key, value in config[section].items():
                    if isinstance(value, dict) and 'extends' in value:
                        parent_section = self._load_extends_path(value['extends'])
                        value_without_extends = {k: v for k, v in value.items() if k != 'extends'}
                        config[section][key] = self._deep_merge(parent_section, value_without_extends)

        return config

    def _load_extends_path(self, path: str) -> Dict[str, Any]:
        """
        Load configuration from extends path.

        Example paths:
        - '_base.securities.schema' -> loads _base/securities/schema.yaml
        - '_base.securities._dim_security' -> loads _base/securities/schema.yaml,
          then navigates to dimensions._dim_security
        """
        parts = path.split('.')

        if len(parts) < 2:
            logger.warning(f"Invalid extends path: {path}")
            return {}

        # Determine if last part is a key or file
        # Convention: keys starting with '_' are template names
        if parts[-1].startswith('_'):
            # It's a key reference: _base.securities._dim_security
            # Load file: _base/securities/schema.yaml
            # Navigate to: dimensions._dim_security

            # Find which file to load (schema, graph, or measures)
            key = parts[-1]
            dir_parts = parts[:-1]

            # Try to infer file type from key pattern
            if key.startswith('_dim'):
                file_name = 'schema.yaml'
                section = 'dimensions'
            elif key.startswith('_fact'):
                file_name = 'schema.yaml'
                section = 'facts'
            elif key.endswith('_base'):
                file_name = 'graph.yaml'
                section = 'nodes'
            else:
                # Default to schema
                file_name = 'schema.yaml'
                section = 'dimensions'

            dir_path = '/'.join(dir_parts)
            file_path = self.models_dir / dir_path / file_name

            if file_path.exists():
                config = self._load_yaml(file_path)
                # Navigate to section and key
                if section in config and key in config[section]:
                    return config[section][key]
                elif key in config:
                    return config[key]
        else:
            # It's a file reference: _base.securities.schema
            file_name = parts[-1]
            dir_parts = parts[:-1]

            dir_path = '/'.join(dir_parts)
            file_path = self.models_dir / dir_path / f'{file_name}.yaml'

            if file_path.exists():
                return self._load_yaml(file_path)

        logger.warning(f"Could not resolve extends path: {path}")
        return {}

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """
        Deep merge two dictionaries.
        Override values take precedence.

        Special handling:
        - Lists are replaced, not merged
        - Dicts are recursively merged
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

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load YAML file."""
        try:
            with open(path, 'r') as f:
                content = yaml.safe_load(f)
                return content if content is not None else {}
        except Exception as e:
            logger.error(f"Error loading YAML from {path}: {e}")
            return {}

    def load_python_measures(self, model_name: str, model_instance=None) -> Optional[Any]:
        """
        Load Python measures module for a model.

        Args:
            model_name: Model name (e.g., 'stocks')
            model_instance: Model instance to pass to measures class

        Returns:
            Measures class instance or None
        """
        config = self.load_model_config(model_name)

        if 'measures' in config and '_python_module' in config['measures']:
            module_path = config['measures']['_python_module']

            # Convert path to module name: 'stocks/measures.py' -> 'models.implemented.stocks.measures'
            module_path = module_path.replace('/', '.').replace('.py', '')
            full_module = f'models.implemented.{module_path}'

            try:
                module = importlib.import_module(full_module)

                # Look for {ModelName}Measures class
                # e.g., StocksMeasures, OptionsMeasures
                class_name = f"{model_name.title()}Measures"
                if hasattr(module, class_name):
                    measures_class = getattr(module, class_name)
                    if model_instance:
                        return measures_class(model_instance)
                    else:
                        return measures_class
                else:
                    logger.warning(f"Python measures class '{class_name}' not found in {full_module}")
            except ImportError as e:
                logger.warning(f"Could not import Python measures from {full_module}: {e}")

        return None

    def clear_cache(self):
        """Clear the configuration cache."""
        self._cache.clear()
