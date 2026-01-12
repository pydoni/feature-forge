"""Tests for registry Pydantic models."""

import pytest
from pydantic import ValidationError

from feature_forge.registry.models import (
    Aggregation,
    Entity,
    Feature,
    FeatureView,
    Source,
)


class TestEntity:
    def test_basic(self):
        e = Entity(name="customer", join_keys=["customer_id"])
        assert e.name == "customer"
        assert e.join_keys == ["customer_id"]
        assert e.description == ""

    def test_composite_keys(self):
        e = Entity(name="order", join_keys=["customer_id", "product_id"])
        assert len(e.join_keys) == 2

    def test_with_description(self):
        e = Entity(name="customer", join_keys=["id"], description="A customer")
        assert e.description == "A customer"


class TestSource:
    def test_parquet_source(self):
        s = Source(
            name="txn",
            backend="parquet",
            path="data/txn.parquet",
            entity="customer",
            timestamp_column="ts",
            columns=[],
        )
        assert s.backend == "parquet"
        assert s.path == "data/txn.parquet"

    def test_parquet_default_backend(self):
        s = Source(
            name="txn",
            path="data/txn.parquet",
            entity="customer",
            timestamp_column="ts",
            columns=[],
        )
        assert s.backend == "parquet"

    def test_parquet_requires_path(self):
        with pytest.raises(ValidationError, match="Parquet backend requires 'path'"):
            Source(
                name="txn",
                backend="parquet",
                entity="customer",
                timestamp_column="ts",
                columns=[],
            )

    def test_s3_requires_uri(self):
        with pytest.raises(ValidationError, match="S3 backend requires 'uri'"):
            Source(
                name="txn",
                backend="s3",
                entity="customer",
                timestamp_column="ts",
                columns=[],
            )

    def test_sql_requires_connection_string(self):
        with pytest.raises(ValidationError, match="SQL backend requires 'connection_string'"):
            Source(
                name="txn",
                backend="sql",
                entity="customer",
                timestamp_column="ts",
                columns=[],
            )

    def test_databricks_requires_table(self):
        with pytest.raises(ValidationError, match="Databricks backend requires 'table'"):
            Source(
                name="txn",
                backend="databricks",
                entity="customer",
                timestamp_column="ts",
                columns=[],
            )

    def test_get_column_names(self):
        from feature_forge.registry.models import Column

        s = Source(
            name="txn",
            path="data/txn.parquet",
            entity="customer",
            timestamp_column="ts",
            columns=[
                Column(name="id", dtype="int64"),
                Column(name="amount", dtype="float64"),
            ],
        )
        assert s.get_column_names() == ["id", "amount"]


class TestAggregation:
    def test_valid_windows(self):
        for w in ["7d", "30d", "24h", "60m", "1d", "365d"]:
            agg = Aggregation(function="count", column="x", window=w)
            assert agg.window == w

    def test_invalid_windows(self):
        for w in ["7", "d7", "7days", "7s", "abc", ""]:
            with pytest.raises(ValidationError):
                Aggregation(function="count", column="x", window=w)

    def test_window_to_interval(self):
        agg = Aggregation(function="count", column="x", window="7d")
        assert agg.window_to_interval() == "7 days"

        agg = Aggregation(function="count", column="x", window="24h")
        assert agg.window_to_interval() == "24 hours"

        agg = Aggregation(function="count", column="x", window="60m")
        assert agg.window_to_interval() == "60 minutes"


class TestFeature:
    def test_passthrough(self):
        f = Feature(name="age", dtype="int32", column="age")
        assert f.column == "age"
        assert f.aggregation is None

    def test_aggregation(self):
        f = Feature(
            name="count_7d",
            dtype="int64",
            aggregation=Aggregation(function="count", column="amount", window="7d"),
        )
        assert f.aggregation is not None
        assert f.column is None

    def test_neither_mode_fails(self):
        with pytest.raises(ValidationError, match="exactly one"):
            Feature(name="bad", dtype="int64")

    def test_both_modes_fails(self):
        with pytest.raises(ValidationError, match="exactly one"):
            Feature(
                name="bad",
                dtype="int64",
                column="x",
                aggregation=Aggregation(function="count", column="x", window="7d"),
            )


class TestFeatureView:
    def test_basic(self):
        fv = FeatureView(
            name="txn_features",
            entity="customer",
            source="transactions",
            features=[Feature(name="age", dtype="int32", column="age")],
        )
        assert fv.name == "txn_features"
        assert fv.timestamp_column is None
