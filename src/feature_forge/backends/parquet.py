"""Parquet backend: reads local Parquet files via DuckDB."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import duckdb

from feature_forge.backends.base import ValidationIssue

if TYPE_CHECKING:
    from feature_forge.registry.models import Source


class ParquetBackend:
    """Backend for local Parquet files."""

    def register_source(
        self,
        conn: duckdb.DuckDBPyConnection,
        source: Source,
        view_name: str,
    ) -> None:
        path = source.path
        if path is None:
            raise ValueError(f"Source '{source.name}' has no 'path' configured")
        conn.execute(
            f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM read_parquet('{path}')"
        )

    def validate_source(self, source: Source, repo_path: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if source.path is None:
            issues.append(ValidationIssue(source.name, "Missing 'path' for parquet backend"))
            return issues

        resolved = Path(source.path)
        if not resolved.is_absolute():
            resolved = Path(repo_path) / resolved

        if not resolved.exists():
            issues.append(
                ValidationIssue(source.name, f"Parquet file not found: {resolved}")
            )
            return issues

        try:
            conn = duckdb.connect(":memory:")
            actual_columns = conn.execute(
                f"SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet('{resolved}'))"
            ).fetchall()
            conn.close()
            actual_names = {row[0] for row in actual_columns}

            declared_names = {c.name for c in source.columns}
            missing = declared_names - actual_names
            if missing:
                issues.append(
                    ValidationIssue(
                        source.name,
                        f"Declared columns not found in Parquet: {sorted(missing)}",
                    )
                )
        except Exception as e:
            issues.append(
                ValidationIssue(source.name, f"Error reading Parquet file: {e}")
            )

        return issues
