"""Shared types, enums, and type aliases for feature-forge."""

from __future__ import annotations

from enum import StrEnum
from typing import TypeAlias


class AggFunction(StrEnum):
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT_DISTINCT = "count_distinct"


class DType(StrEnum):
    INT32 = "int32"
    INT64 = "int64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    VARCHAR = "varchar"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    DATE = "date"


class BackendType(StrEnum):
    PARQUET = "parquet"
    S3 = "s3"
    SQL = "sql"
    DATABRICKS = "databricks"


class EngineType(StrEnum):
    DUCKDB = "duckdb"
    SPARK = "spark"


JoinKeys: TypeAlias = dict[str, str | int]
