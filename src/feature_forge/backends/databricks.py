"""Databricks backend: reads from Unity Catalog tables via SQL Warehouse or dbutils.

Two modes (auto-detected):
1. Outside Databricks (default): uses databricks-sql-connector to query via SQL Warehouse.
   Result comes as Arrow, registered in DuckDB.
2. Inside Databricks (DATABRICKS_RUNTIME_VERSION env var): uses spark.sql() directly.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import duckdb

from feature_forge.backends.base import ValidationIssue
from feature_forge.exceptions import BackendError

if TYPE_CHECKING:
    from feature_forge.registry.models import Source


def _is_inside_databricks() -> bool:
    return "DATABRICKS_RUNTIME_VERSION" in os.environ


class DatabricksBackend:
    """Backend for Databricks Unity Catalog tables."""

    def _get_credentials(self, source: Source) -> tuple[str, str, str]:
        """Resolve host, warehouse_id, and token from source config or env vars."""
        host = source.host or os.environ.get("DATABRICKS_HOST", "")
        warehouse_id = source.warehouse_id or os.environ.get(
            "DATABRICKS_WAREHOUSE_ID", ""
        )
        token = os.environ.get("DATABRICKS_TOKEN", "")

        if not host:
            raise BackendError(
                f"Databricks source '{source.name}': 'host' not configured and "
                f"DATABRICKS_HOST env var not set"
            )
        if not token and not _is_inside_databricks():
            raise BackendError(
                f"Databricks source '{source.name}': DATABRICKS_TOKEN env var not set"
            )

        return host, warehouse_id, token

    def _query_via_connector(
        self, source: Source, host: str, warehouse_id: str, token: str
    ) -> "pyarrow.Table":
        """Query Databricks via SQL Warehouse using databricks-sql-connector."""
        try:
            from databricks import sql as databricks_sql
        except ImportError as e:
            raise BackendError(
                "Databricks backend requires databricks-sql-connector. "
                "Install with: pip install feature-forge[databricks]"
            ) from e

        table = source.table
        if table is None:
            raise BackendError(
                f"Databricks source '{source.name}' has no 'table' configured"
            )

        connection_params: dict[str, str] = {
            "server_hostname": host,
            "access_token": token,
        }
        if warehouse_id:
            connection_params["http_path"] = f"/sql/1.0/warehouses/{warehouse_id}"

        try:
            with databricks_sql.connect(**connection_params) as conn:
                with conn.cursor() as cursor:
                    query = source.query or f"SELECT * FROM {table}"
                    cursor.execute(query)
                    return cursor.fetchall_arrow()
        except Exception as e:
            raise BackendError(
                f"Failed to query Databricks for source '{source.name}': {e}"
            ) from e

    def _query_via_spark(self, source: Source) -> "pandas.DataFrame":
        """Query via spark.sql() when running inside a Databricks notebook."""
        try:
            from pyspark.sql import SparkSession

            spark = SparkSession.getActiveSession()
            if spark is None:
                raise BackendError(
                    "No active Spark session found inside Databricks runtime"
                )

            table = source.table
            if table is None:
                raise BackendError(
                    f"Databricks source '{source.name}' has no 'table' configured"
                )

            query = source.query or f"SELECT * FROM {table}"
            return spark.sql(query).toPandas()
        except ImportError as e:
            raise BackendError(
                f"PySpark not available inside Databricks runtime: {e}"
            ) from e

    def register_source(
        self,
        conn: duckdb.DuckDBPyConnection,
        source: Source,
        view_name: str,
        repo_path: str = "",
    ) -> None:
        if _is_inside_databricks():
            df = self._query_via_spark(source)
            conn.register(view_name, df)
        else:
            host, warehouse_id, token = self._get_credentials(source)
            arrow_table = self._query_via_connector(
                source, host, warehouse_id, token
            )
            conn.register(view_name, arrow_table)

    def validate_source(self, source: Source, repo_path: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if source.table is None:
            issues.append(
                ValidationIssue(
                    source.name, "Missing 'table' for Databricks backend"
                )
            )

        if not _is_inside_databricks():
            host = source.host or os.environ.get("DATABRICKS_HOST", "")
            token = os.environ.get("DATABRICKS_TOKEN", "")

            if not host:
                issues.append(
                    ValidationIssue(
                        source.name,
                        "Databricks 'host' not configured and DATABRICKS_HOST env var not set",
                        level="warning",
                    )
                )
            if not token:
                issues.append(
                    ValidationIssue(
                        source.name,
                        "DATABRICKS_TOKEN env var not set (required outside Databricks)",
                        level="warning",
                    )
                )

        return issues
