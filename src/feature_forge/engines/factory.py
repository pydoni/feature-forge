"""Factory for query engines."""

from __future__ import annotations

from feature_forge.engines.base import Engine
from feature_forge.engines.duckdb_engine import DuckDBEngine
from feature_forge.exceptions import EngineError
from feature_forge.types import EngineType


def get_engine(engine_type: EngineType | str = EngineType.DUCKDB) -> Engine:
    """Get an engine instance by type name."""
    try:
        et = EngineType(engine_type)
    except ValueError:
        valid = ", ".join(e.value for e in EngineType)
        raise EngineError(
            f"Unknown engine type: '{engine_type}'. Valid options: {valid}"
        ) from None

    if et == EngineType.DUCKDB:
        return DuckDBEngine()

    if et == EngineType.SPARK:
        try:
            from feature_forge.engines.spark_engine import SparkEngine

            return SparkEngine()
        except ImportError as e:
            raise EngineError(
                "Spark engine requires PySpark. "
                "Install with: pip install fforge[spark]"
            ) from e

    raise EngineError(f"Unknown engine type: {engine_type}")
