"""SQL backend: reads from SQLite/PostgreSQL databases via DuckDB extensions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb

from feature_forge.backends.base import ValidationIssue
from feature_forge.exceptions import BackendError

if TYPE_CHECKING:
    from feature_forge.registry.models import Source


class SQLBackend:
    """Backend for SQL databases (SQLite, PostgreSQL).

    Uses DuckDB's ATTACH to connect to external databases and expose
    tables/queries as DuckDB views.

    Supported connection strings:
    - SQLite: path to .db file (e.g., "data/events.db")
    - PostgreSQL: standard connection string (e.g., "host=localhost dbname=mydb")
    """

    def __init__(self) -> None:
        self._attached_dbs: set[str] = set()

    def _detect_db_type(self, connection_string: str) -> str:
        """Detect database type from connection string."""
        cs_lower = connection_string.lower()
        if cs_lower.endswith((".db", ".sqlite", ".sqlite3")) or "sqlite" in cs_lower:
            return "SQLITE"
        if any(kw in cs_lower for kw in ("host=", "postgresql://", "postgres://")):
            return "POSTGRES"
        # Default to SQLite for file paths
        return "SQLITE"

    def _ensure_extension(self, conn: duckdb.DuckDBPyConnection, db_type: str) -> None:
        ext_name = db_type.lower()
        if ext_name == "sqlite":
            return  # Built-in, no extension needed
        try:
            conn.execute(f"INSTALL {ext_name}; LOAD {ext_name};")
        except duckdb.IOException:
            conn.execute(f"LOAD {ext_name};")

    def register_source(
        self,
        conn: duckdb.DuckDBPyConnection,
        source: Source,
        view_name: str,
        repo_path: str = "",
    ) -> None:
        cs = source.connection_string
        if cs is None:
            raise BackendError(
                f"Source '{source.name}' has no 'connection_string' configured"
            )

        db_type = self._detect_db_type(cs)
        self._ensure_extension(conn, db_type)

        # Use source name as the attached db alias
        db_alias = f"__sqldb_{source.name}"

        if db_alias not in self._attached_dbs:
            # Resolve relative paths for SQLite
            if db_type == "SQLITE":
                from pathlib import Path

                resolved = Path(cs)
                if not resolved.is_absolute() and repo_path:
                    resolved = Path(repo_path) / resolved
                cs = str(resolved)

            conn.execute(f"ATTACH '{cs}' AS {db_alias} (TYPE {db_type}, READ_ONLY);")
            self._attached_dbs.add(db_alias)

        # Create view from query or full table
        if source.query:
            conn.execute(
                f"CREATE OR REPLACE VIEW {view_name} AS {source.query}"
            )
        elif source.table:
            conn.execute(
                f"CREATE OR REPLACE VIEW {view_name} AS "
                f"SELECT * FROM {db_alias}.{source.table}"
            )
        else:
            raise BackendError(
                f"SQL source '{source.name}' must have either 'query' or 'table' configured"
            )

    def validate_source(self, source: Source, repo_path: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if source.connection_string is None:
            issues.append(
                ValidationIssue(
                    source.name, "Missing 'connection_string' for SQL backend"
                )
            )
            return issues

        if not source.query and not source.table:
            issues.append(
                ValidationIssue(
                    source.name,
                    "SQL source must have either 'query' or 'table' configured",
                )
            )

        # Try to verify SQLite file exists
        db_type = self._detect_db_type(source.connection_string)
        if db_type == "SQLITE":
            from pathlib import Path

            resolved = Path(source.connection_string)
            if not resolved.is_absolute() and repo_path:
                resolved = Path(repo_path) / resolved
            if not resolved.exists():
                issues.append(
                    ValidationIssue(
                        source.name,
                        f"SQLite database not found: {resolved}",
                    )
                )

        return issues
