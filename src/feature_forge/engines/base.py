"""Base protocol for query engines."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class Engine(Protocol):
    """Protocol that all query engines must implement."""

    def connect(self) -> None:
        """Initialize the engine connection."""
        ...

    def close(self) -> None:
        """Close the engine connection and release resources."""
        ...

    def register_view(self, view_name: str, data: Any) -> None:
        """Register a DataFrame or file as a named view in the engine."""
        ...

    def execute_sql(self, sql: str) -> pd.DataFrame:
        """Execute a SQL query and return the result as a DataFrame."""
        ...

    def write_parquet(self, sql: str, path: str) -> None:
        """Execute a SQL query and write the result to a Parquet file."""
        ...
