"""Base protocol for source backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import duckdb

    from feature_forge.registry.models import Source


@dataclass
class ValidationIssue:
    """A validation issue found by a backend."""

    source_name: str
    message: str
    level: str = "error"  # "error" or "warning"


@runtime_checkable
class SourceBackend(Protocol):
    """Protocol that all source backends must implement."""

    def register_source(
        self,
        conn: duckdb.DuckDBPyConnection,
        source: Source,
        view_name: str,
        repo_path: str = "",
    ) -> None:
        """Register the source as a DuckDB view so the engine can query it."""
        ...

    def validate_source(self, source: Source, repo_path: str) -> list[ValidationIssue]:
        """Validate that the source is accessible and its schema matches declarations."""
        ...
