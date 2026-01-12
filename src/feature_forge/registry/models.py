"""Pydantic models for the feature registry YAML schema."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, field_validator, model_validator

from feature_forge.types import AggFunction, BackendType, DType


class Entity(BaseModel):
    """An entity represents the subject of features (e.g. customer, merchant)."""

    name: str
    join_keys: list[str]
    description: str = ""


class Column(BaseModel):
    """A column declaration in a source."""

    name: str
    dtype: DType


class Source(BaseModel):
    """A data source that provides raw data for feature computation."""

    name: str
    backend: BackendType = BackendType.PARQUET
    entity: str
    timestamp_column: str
    columns: list[Column]

    # Backend-specific fields (validated per backend)
    path: str | None = None
    uri: str | None = None
    table: str | None = None
    connection_string: str | None = None
    query: str | None = None
    host: str | None = None
    warehouse_id: str | None = None

    @model_validator(mode="after")
    def validate_backend_fields(self) -> Source:
        if self.backend == BackendType.PARQUET and not self.path:
            raise ValueError("Parquet backend requires 'path'")
        if self.backend == BackendType.S3 and not self.uri:
            raise ValueError("S3 backend requires 'uri'")
        if self.backend == BackendType.SQL and not self.connection_string:
            raise ValueError("SQL backend requires 'connection_string'")
        if self.backend == BackendType.DATABRICKS and not self.table:
            raise ValueError("Databricks backend requires 'table'")
        return self

    def get_column_names(self) -> list[str]:
        return [c.name for c in self.columns]


_WINDOW_PATTERN = re.compile(r"^(\d+)(d|h|m)$")


class Aggregation(BaseModel):
    """An aggregation specification for a feature."""

    function: AggFunction
    column: str
    window: str

    @field_validator("window")
    @classmethod
    def validate_window(cls, v: str) -> str:
        if not _WINDOW_PATTERN.match(v):
            raise ValueError(
                f"Invalid window '{v}'. Must match pattern '<int><unit>' "
                f"where unit is d (days), h (hours), or m (minutes). Examples: '7d', '24h', '60m'"
            )
        return v

    def window_to_interval(self) -> str:
        """Convert window string to SQL INTERVAL string."""
        match = _WINDOW_PATTERN.match(self.window)
        assert match is not None
        value, unit = match.group(1), match.group(2)
        unit_map = {"d": "days", "h": "hours", "m": "minutes"}
        return f"{value} {unit_map[unit]}"


class Feature(BaseModel):
    """A single feature definition within a feature view."""

    name: str
    dtype: DType
    description: str = ""
    column: str | None = None
    aggregation: Aggregation | None = None

    @model_validator(mode="after")
    def exactly_one_mode(self) -> Feature:
        has_column = self.column is not None
        has_agg = self.aggregation is not None
        if has_column == has_agg:
            raise ValueError(
                f"Feature '{self.name}' must have exactly one of 'column' (passthrough) "
                f"or 'aggregation', not {'both' if has_column else 'neither'}"
            )
        return self


class FeatureView(BaseModel):
    """A feature view groups features computed from a single source."""

    name: str
    entity: str
    source: str
    timestamp_column: str | None = None
    features: list[Feature]


class FeatureRegistry(BaseModel):
    """The complete parsed feature registry."""

    entities: list[Entity] = []
    sources: list[Source] = []
    feature_views: list[FeatureView] = []
    engine: Literal["duckdb", "spark"] = "duckdb"

    def get_entity(self, name: str) -> Entity | None:
        return next((e for e in self.entities if e.name == name), None)

    def get_source(self, name: str) -> Source | None:
        return next((s for s in self.sources if s.name == name), None)

    def get_feature_view(self, name: str) -> FeatureView | None:
        return next((fv for fv in self.feature_views if fv.name == name), None)
