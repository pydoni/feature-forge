"""Factory for source backends."""

from __future__ import annotations

from feature_forge.backends.base import SourceBackend
from feature_forge.backends.parquet import ParquetBackend
from feature_forge.exceptions import BackendError
from feature_forge.types import BackendType


def _import_s3_backend() -> type:
    from feature_forge.backends.s3 import S3Backend

    return S3Backend


def _import_sql_backend() -> type:
    from feature_forge.backends.sql import SQLBackend

    return SQLBackend


def _import_databricks_backend() -> type:
    from feature_forge.backends.databricks import DatabricksBackend

    return DatabricksBackend


_BACKEND_FACTORIES: dict[BackendType, type | callable] = {
    BackendType.PARQUET: ParquetBackend,
    BackendType.S3: _import_s3_backend,
    BackendType.SQL: _import_sql_backend,
    BackendType.DATABRICKS: _import_databricks_backend,
}


def get_backend(backend_type: BackendType | str) -> SourceBackend:
    """Get a backend instance by type name."""
    bt = BackendType(backend_type)
    factory = _BACKEND_FACTORIES.get(bt)
    if factory is None:
        raise BackendError(f"Unknown backend type: {backend_type}")

    if bt == BackendType.PARQUET:
        return ParquetBackend()

    # Lazy-loaded backends
    try:
        cls = factory()
        return cls()
    except ImportError as e:
        extras_map = {
            BackendType.DATABRICKS: "databricks",
            BackendType.SPARK: "spark",
        }
        extra = extras_map.get(bt, str(bt))
        raise BackendError(
            f"Backend '{bt}' requires additional dependencies. "
            f"Install with: pip install feature-forge[{extra}]"
        ) from e
