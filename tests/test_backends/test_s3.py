"""Tests for the S3 backend."""

from feature_forge.backends.s3 import S3Backend
from feature_forge.registry.models import Column, Source


class TestS3BackendValidation:
    def test_valid_s3_uri(self):
        backend = S3Backend()
        source = Source(
            name="logs",
            backend="s3",
            uri="s3://my-bucket/data/*.parquet",
            entity="customer",
            timestamp_column="ts",
            columns=[Column(name="id", dtype="int64")],
        )
        issues = backend.validate_source(source, "/tmp")
        assert len(issues) == 0

    def test_valid_gs_uri(self):
        backend = S3Backend()
        source = Source(
            name="logs",
            backend="s3",
            uri="gs://my-bucket/data/*.parquet",
            entity="customer",
            timestamp_column="ts",
            columns=[Column(name="id", dtype="int64")],
        )
        issues = backend.validate_source(source, "/tmp")
        assert len(issues) == 0

    def test_valid_azure_uri(self):
        backend = S3Backend()
        source = Source(
            name="logs",
            backend="s3",
            uri="az://container/data/*.parquet",
            entity="customer",
            timestamp_column="ts",
            columns=[Column(name="id", dtype="int64")],
        )
        issues = backend.validate_source(source, "/tmp")
        assert len(issues) == 0

    def test_invalid_uri_scheme(self):
        backend = S3Backend()
        source = Source(
            name="logs",
            backend="s3",
            uri="http://example.com/data.parquet",
            entity="customer",
            timestamp_column="ts",
            columns=[Column(name="id", dtype="int64")],
        )
        issues = backend.validate_source(source, "/tmp")
        assert any("must start with" in i.message for i in issues)

    def test_missing_uri(self):
        backend = S3Backend()
        source = Source(
            name="logs",
            backend="s3",
            uri="s3://placeholder",  # need valid uri to pass model validation
            entity="customer",
            timestamp_column="ts",
            columns=[],
        )
        # Simulate missing uri
        source.uri = None
        issues = backend.validate_source(source, "/tmp")
        assert any("Missing 'uri'" in i.message for i in issues)
