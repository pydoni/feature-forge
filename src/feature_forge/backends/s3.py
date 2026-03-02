"""S3 backend: reads Parquet files from S3/GCS/Azure via DuckDB httpfs extension."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import duckdb

from feature_forge.backends.base import ValidationIssue
from feature_forge.exceptions import BackendError

if TYPE_CHECKING:
    from feature_forge.registry.models import Source


class S3Backend:
    """Backend for cloud object storage (S3, GCS, Azure Blob).

    Uses DuckDB's httpfs extension to read Parquet files directly from
    cloud URIs like s3://bucket/path/*.parquet.

    Authentication is resolved from environment variables:
    - AWS: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
    - GCS: reads from default credentials
    - Azure: AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT
    """

    def _ensure_httpfs(self, conn: duckdb.DuckDBPyConnection) -> None:
        try:
            conn.execute("INSTALL httpfs; LOAD httpfs;")
        except duckdb.IOException:
            # Already installed, just load
            conn.execute("LOAD httpfs;")

    def _configure_credentials(self, conn: duckdb.DuckDBPyConnection, uri: str) -> None:
        """Configure cloud credentials based on the URI scheme."""
        if uri.startswith("s3://"):
            region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", ""))
            key_id = os.environ.get("AWS_ACCESS_KEY_ID", "")
            secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
            if region:
                conn.execute(f"SET s3_region = '{region}';")
            if key_id and secret:
                conn.execute(f"SET s3_access_key_id = '{key_id}';")
                conn.execute(f"SET s3_secret_access_key = '{secret}';")
            session_token = os.environ.get("AWS_SESSION_TOKEN", "")
            if session_token:
                conn.execute(f"SET s3_session_token = '{session_token}';")
        elif uri.startswith("gs://") or uri.startswith("gcs://"):
            # GCS uses S3-compatible API through DuckDB
            conn.execute("SET s3_endpoint = 'storage.googleapis.com';")
        elif uri.startswith("az://") or uri.startswith("abfss://"):
            conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
            if conn_str:
                conn.execute(f"SET azure_storage_connection_string = '{conn_str}';")

    def register_source(
        self,
        conn: duckdb.DuckDBPyConnection,
        source: Source,
        view_name: str,
        repo_path: str = "",
    ) -> None:
        uri = source.uri
        if uri is None:
            raise BackendError(f"Source '{source.name}' has no 'uri' configured")

        self._ensure_httpfs(conn)
        self._configure_credentials(conn, uri)

        conn.execute(
            f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM read_parquet('{uri}')"
        )

    def validate_source(self, source: Source, repo_path: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if source.uri is None:
            issues.append(ValidationIssue(source.name, "Missing 'uri' for S3 backend"))
            return issues

        valid_schemes = ("s3://", "gs://", "gcs://", "az://", "abfss://")
        if not source.uri.startswith(valid_schemes):
            issues.append(
                ValidationIssue(
                    source.name,
                    f"URI must start with one of {valid_schemes}, got: {source.uri}",
                )
            )

        return issues
