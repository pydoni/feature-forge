"""feature-forge: Lightweight feature store for small and medium teams."""

from feature_forge.exceptions import (
    BackendError,
    EngineError,
    FeatureForgeError,
    MaterializationError,
    RegistryError,
    ValidationError,
)
from feature_forge.registry.loader import load_registry
from feature_forge.registry.models import (
    Aggregation,
    Column,
    Entity,
    Feature,
    FeatureRegistry,
    FeatureView,
    Source,
)
from feature_forge.sdk.store import FeatureStore
from feature_forge.types import AggFunction, BackendType, DType, EngineType

__version__ = "0.1.0"

__all__ = [
    "AggFunction",
    "Aggregation",
    "BackendError",
    "BackendType",
    "Column",
    "DType",
    "EngineError",
    "EngineType",
    "Entity",
    "Feature",
    "FeatureForgeError",
    "FeatureRegistry",
    "FeatureStore",
    "FeatureView",
    "MaterializationError",
    "RegistryError",
    "Source",
    "ValidationError",
    "load_registry",
]
