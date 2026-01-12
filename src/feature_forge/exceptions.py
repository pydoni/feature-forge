"""Exception hierarchy for feature-forge."""


class FeatureForgeError(Exception):
    """Base exception for all feature-forge errors."""


class RegistryError(FeatureForgeError):
    """Error loading or parsing the feature registry YAML files."""


class ValidationError(FeatureForgeError):
    """Schema or cross-reference validation failure."""


class BackendError(FeatureForgeError):
    """Source backend error (connection, read, registration)."""


class EngineError(FeatureForgeError):
    """Query engine error (DuckDB, Spark)."""


class MaterializationError(EngineError):
    """Error during feature materialization."""
