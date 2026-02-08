"""DuckDB query engine implementation."""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from feature_forge.exceptions import EngineError


class DuckDBEngine:
    """Query engine backed by DuckDB (in-process, zero-config)."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self.connect()
        assert self._conn is not None
        return self._conn

    def connect(self) -> None:
        if self._conn is not None:
            return
        try:
            self._conn = duckdb.connect(self._db_path)
        except Exception as e:
            raise EngineError(f"Failed to connect to DuckDB: {e}") from e

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def register_view(self, view_name: str, data: Any) -> None:
        """Register data as a named view.

        Supports:
        - pandas DataFrame: registered as a temporary table
        - str (file path): registered as a view over read_parquet()
        """
        if isinstance(data, pd.DataFrame):
            self.conn.register(view_name, data)
        elif isinstance(data, str):
            self.conn.execute(
                f"CREATE OR REPLACE VIEW {view_name} AS "
                f"SELECT * FROM read_parquet('{data}')"
            )
        else:
            raise EngineError(
                f"Cannot register data of type {type(data).__name__}. "
                f"Expected pandas DataFrame or file path string."
            )

    def execute_sql(self, sql: str) -> pd.DataFrame:
        try:
            return self.conn.execute(sql).fetchdf()
        except Exception as e:
            raise EngineError(f"SQL execution failed: {e}\nQuery:\n{sql}") from e

    def write_parquet(self, sql: str, path: str) -> None:
        try:
            self.conn.execute(f"COPY ({sql}) TO '{path}' (FORMAT PARQUET)")
        except Exception as e:
            raise EngineError(f"Failed to write Parquet to {path}: {e}") from e

    def __enter__(self) -> DuckDBEngine:
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
