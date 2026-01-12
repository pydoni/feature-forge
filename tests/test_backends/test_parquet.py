"""Tests for the Parquet backend."""

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from feature_forge.backends.parquet import ParquetBackend
from feature_forge.registry.models import Column, Source


@pytest.fixture
def parquet_backend() -> ParquetBackend:
    return ParquetBackend()


@pytest.fixture
def parquet_source(sample_transactions: Path) -> Source:
    return Source(
        name="txn",
        backend="parquet",
        path=str(sample_transactions),
        entity="customer",
        timestamp_column="event_timestamp",
        columns=[
            Column(name="customer_id", dtype="int64"),
            Column(name="amount", dtype="float64"),
            Column(name="event_timestamp", dtype="timestamp"),
        ],
    )


class TestParquetBackend:
    def test_register_source(
        self, parquet_backend: ParquetBackend, parquet_source: Source
    ):
        conn = duckdb.connect(":memory:")
        parquet_backend.register_source(conn, parquet_source, "txn_view")
        result = conn.execute("SELECT COUNT(*) FROM txn_view").fetchone()
        assert result is not None
        assert result[0] == 5
        conn.close()

    def test_register_source_columns_accessible(
        self, parquet_backend: ParquetBackend, parquet_source: Source
    ):
        conn = duckdb.connect(":memory:")
        parquet_backend.register_source(conn, parquet_source, "txn_view")
        result = conn.execute("SELECT customer_id, amount FROM txn_view LIMIT 1").fetchone()
        assert result is not None
        assert len(result) == 2
        conn.close()

    def test_validate_source_valid(
        self, parquet_backend: ParquetBackend, parquet_source: Source
    ):
        repo_path = str(Path(parquet_source.path).parent)
        issues = parquet_backend.validate_source(parquet_source, repo_path)
        errors = [i for i in issues if i.level == "error"]
        assert len(errors) == 0

    def test_validate_source_missing_file(self, parquet_backend: ParquetBackend):
        source = Source(
            name="missing",
            backend="parquet",
            path="/tmp/nonexistent_file_12345.parquet",
            entity="customer",
            timestamp_column="ts",
            columns=[],
        )
        issues = parquet_backend.validate_source(source, "/tmp")
        assert any("not found" in i.message for i in issues)

    def test_validate_source_missing_columns(
        self, parquet_backend: ParquetBackend, sample_transactions: Path
    ):
        source = Source(
            name="txn",
            backend="parquet",
            path=str(sample_transactions),
            entity="customer",
            timestamp_column="ts",
            columns=[
                Column(name="customer_id", dtype="int64"),
                Column(name="fake_column", dtype="varchar"),
            ],
        )
        repo_path = str(sample_transactions.parent)
        issues = parquet_backend.validate_source(source, repo_path)
        assert any("fake_column" in i.message for i in issues)

    def test_validate_relative_path(
        self, parquet_backend: ParquetBackend, sample_transactions: Path
    ):
        source = Source(
            name="txn",
            backend="parquet",
            path="transactions.parquet",
            entity="customer",
            timestamp_column="ts",
            columns=[Column(name="customer_id", dtype="int64")],
        )
        repo_path = str(sample_transactions.parent)
        issues = parquet_backend.validate_source(source, repo_path)
        errors = [i for i in issues if i.level == "error"]
        assert len(errors) == 0
