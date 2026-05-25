"""Factory for source backends."""

from __future__ import annotations

from collections.abc import Callable

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
    try:
        from feature_forge.backends.databricks import DatabricksBackend
        return DatabricksBackend
    except ImportError as e:
        raise BackendError(
            "Databricks backend requires databricks-sql-connector. "
            "Install with: pip install feature-forge[databricks]"
        ) from e


_BACKEND_FACTORIES: dict[BackendType, type | Callable[[], type]] = {
    BackendType.PARQUET: ParquetBackend,
    BackendType.S3: _import_s3_backend,
    BackendType.SQL: _import_sql_backend,
    BackendType.DATABRICKS: _import_databricks_backend,
}


def get_backend(backend_type: BackendType | str) -> SourceBackend:
    """Get a backend instance by type name."""
    try:
        bt = BackendType(backend_type)
    except ValueError:
        raise BackendError(
            f"Unknown backend type: '{backend_type}'. "
            f"Valid options: {', '.join(e.value for e in BackendType)}"
        ) from None
    factory = _BACKEND_FACTORIES.get(bt)
    if factory is None:
        raise BackendError(f"Unknown backend type: {backend_type}")

    if bt == BackendType.PARQUET:
        return ParquetBackend()

    # Lazy-loaded backends
    try:
        cls = factory()
        return cls()
    except BackendError:
        raise
    except ImportError as e:
        raise BackendError(
            f"Backend '{bt}' requires additional dependencies. "
            f"Install with: pip install feature-forge[{bt}]"
        ) from e
