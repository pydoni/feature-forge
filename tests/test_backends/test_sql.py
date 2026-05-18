"""Tests for the SQL backend (SQLite integration)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import duckdb
import pytest

from feature_forge.backends.sql import SQLBackend
from feature_forge.registry.models import Column, Source


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    """Create a SQLite database with test data."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE events ("
        "  customer_id INTEGER, "
        "  event_type TEXT, "
        "  created_at TEXT"
        ")"
    )
    conn.executemany(
        "INSERT INTO events VALUES (?, ?, ?)",
        [
            (1, "login", "2025-01-01 10:00:00"),
            (1, "purchase", "2025-01-05 14:30:00"),
            (2, "login", "2025-01-03 08:00:00"),
            (2, "signup", "2025-01-02 12:00:00"),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def sql_backend() -> SQLBackend:
    return SQLBackend()


class TestSQLBackendRegister:
    def test_register_sqlite_with_query(
        self, sql_backend: SQLBackend, sqlite_db: Path
    ):
        source = Source(
            name="events",
            backend="sql",
            connection_string=str(sqlite_db),
            query="SELECT * FROM __sqldb_events.events",
            entity="customer",
            timestamp_column="created_at",
            columns=[
                Column(name="customer_id", dtype="int64"),
                Column(name="event_type", dtype="varchar"),
                Column(name="created_at", dtype="timestamp"),
            ],
        )

        conn = duckdb.connect(":memory:")
        sql_backend.register_source(conn, source, "events_view")

        result = conn.execute("SELECT COUNT(*) FROM events_view").fetchone()
        assert result is not None
        assert result[0] == 4
        conn.close()

    def test_register_sqlite_columns_match(
        self, sqlite_db: Path
    ):
        backend = SQLBackend()
        source = Source(
            name="events2",
            backend="sql",
            connection_string=str(sqlite_db),
            query="SELECT * FROM __sqldb_events2.events",
            entity="customer",
            timestamp_column="created_at",
            columns=[],
        )

        conn = duckdb.connect(":memory:")
        backend.register_source(conn, source, "events_view")

        result = conn.execute(
            "SELECT customer_id, event_type FROM events_view WHERE customer_id = 1"
        ).fetchall()
        assert len(result) == 2
        conn.close()


class TestSQLBackendValidation:
    def test_validate_existing_sqlite(
        self, sql_backend: SQLBackend, sqlite_db: Path
    ):
        source = Source(
            name="events",
            backend="sql",
            connection_string=str(sqlite_db),
            query="SELECT * FROM events",
            entity="customer",
            timestamp_column="created_at",
            columns=[],
        )
        issues = sql_backend.validate_source(source, str(sqlite_db.parent))
        errors = [i for i in issues if i.level == "error"]
        assert len(errors) == 0

    def test_validate_missing_sqlite_file(self, sql_backend: SQLBackend):
        source = Source(
            name="events",
            backend="sql",
            connection_string="/tmp/nonexistent_db_12345.db",
            query="SELECT * FROM events",
            entity="customer",
            timestamp_column="created_at",
            columns=[],
        )
        issues = sql_backend.validate_source(source, "/tmp")
        assert any("not found" in i.message for i in issues)

    def test_validate_missing_connection_string(self, sql_backend: SQLBackend):
        source = Source(
            name="events",
            backend="sql",
            connection_string="placeholder.db",
            query="SELECT 1",
            entity="customer",
            timestamp_column="created_at",
            columns=[],
        )
        source.connection_string = None
        issues = sql_backend.validate_source(source, "/tmp")
        assert any("Missing 'connection_string'" in i.message for i in issues)

    def test_validate_no_query_or_table(self, sql_backend: SQLBackend, sqlite_db: Path):
        source = Source(
            name="events",
            backend="sql",
            connection_string=str(sqlite_db),
            query="SELECT 1",  # pass model validation
            entity="customer",
            timestamp_column="created_at",
            columns=[],
        )
        # Simulate no query and no table
        source.query = None
        source.table = None
        issues = sql_backend.validate_source(source, "/tmp")
        assert any("either 'query' or 'table'" in i.message for i in issues)

    def test_detect_sqlite_by_extension(self, sql_backend: SQLBackend):
        assert sql_backend._detect_db_type("data.db") == "SQLITE"
        assert sql_backend._detect_db_type("data.sqlite") == "SQLITE"
        assert sql_backend._detect_db_type("data.sqlite3") == "SQLITE"

    def test_detect_postgres(self, sql_backend: SQLBackend):
        assert sql_backend._detect_db_type("host=localhost dbname=mydb") == "POSTGRES"
        assert sql_backend._detect_db_type("postgresql://host/db") == "POSTGRES"
