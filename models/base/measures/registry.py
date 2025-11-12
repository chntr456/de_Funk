"""
Measure registry for dynamic measure type registration.

Provides a factory pattern for creating measure instances from configuration.
"""

from typing import Dict, Type, Any

from .base_measure import BaseMeasure, MeasureType


class MeasureRegistry:
    """
    Registry for measure type implementations.

    Uses decorator pattern for registering measure classes.
    Acts as a factory for creating measure instances from YAML config.

    Example usage:
        @MeasureRegistry.register(MeasureType.SIMPLE)
        class SimpleMeasure(BaseMeasure):
            ...

        # Later:
        measure = MeasureRegistry.create_measure({
            'name': 'avg_close',
            'type': 'simple',
            'source': 'fact_prices.close',
            'aggregation': 'avg'
        })
    """

    # Class-level registry mapping measure types to implementations
    _registry: Dict[MeasureType, Type[BaseMeasure]] = {}

    @classmethod
    def register(cls, measure_type: MeasureType):
        """
        Decorator to register measure implementations.

        Args:
            measure_type: Type of measure this class implements

        Returns:
            Decorator function

        Example:
            @MeasureRegistry.register(MeasureType.SIMPLE)
            class SimpleMeasure(BaseMeasure):
                pass
        """
        def decorator(measure_class: Type[BaseMeasure]):
            # Validate that class implements BaseMeasure
            if not issubclass(measure_class, BaseMeasure):
                raise TypeError(
                    f"Measure class {measure_class.__name__} must inherit from BaseMeasure"
                )

            # Register the class
            cls._registry[measure_type] = measure_class

            # Return class unmodified (standard decorator pattern)
            return measure_class

        return decorator

    @classmethod
    def create_measure(cls, config: Dict[str, Any]) -> BaseMeasure:
        """
        Factory method to create measure from configuration.

        Args:
            config: Measure configuration dictionary from YAML

        Returns:
            Instantiated measure object

        Raises:
            ValueError: If measure type is unknown or not registered
            KeyError: If required config fields are missing

        Example:
            config = {
                'name': 'avg_close',
                'type': 'simple',
                'source': 'fact_prices.close',
                'aggregation': 'avg'
            }
            measure = MeasureRegistry.create_measure(config)
        """
        # Get measure type (default to 'simple' for backward compatibility)
        measure_type_str = config.get('type', 'simple')

        try:
            measure_type = MeasureType(measure_type_str)
        except ValueError:
            raise ValueError(
                f"Unknown measure type: '{measure_type_str}'. "
                f"Valid types: {[t.value for t in MeasureType]}"
            )

        # Look up measure class in registry
        measure_class = cls._registry.get(measure_type)

        if not measure_class:
            raise ValueError(
                f"Measure type '{measure_type_str}' is not registered. "
                f"Registered types: {[t.value for t in cls._registry.keys()]}"
            )

        # Instantiate and return measure
        try:
            return measure_class(config)
        except Exception as e:
            raise ValueError(
                f"Failed to create measure '{config.get('name')}' of type '{measure_type_str}': {e}"
            ) from e

    @classmethod
    def get_registered_types(cls) -> list:
        """
        Get list of registered measure types.

        Returns:
            List of registered MeasureType enums
        """
        return list(cls._registry.keys())

    @classmethod
    def is_registered(cls, measure_type: MeasureType) -> bool:
        """
        Check if a measure type is registered.

        Args:
            measure_type: Measure type to check

        Returns:
            True if registered, False otherwise
        """
        return measure_type in cls._registry

    @classmethod
    def get_measure_class(cls, measure_type: MeasureType) -> Type[BaseMeasure]:
        """
        Get measure class for a given type.

        Args:
            measure_type: Measure type

        Returns:
            Measure class

        Raises:
            ValueError: If measure type not registered
        """
        measure_class = cls._registry.get(measure_type)
        if not measure_class:
            raise ValueError(f"Measure type '{measure_type.value}' is not registered")
        return measure_class
