"""FeatureStore: the main user-facing API for feature-forge."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from feature_forge.engine.retrieval import retrieve_features
from feature_forge.engines.base import Engine
from feature_forge.engines.factory import get_engine
from feature_forge.exceptions import FeatureForgeError, ValidationError
from feature_forge.registry.loader import load_registry
from feature_forge.registry.models import FeatureRegistry
from feature_forge.registry.validator import RegistryValidationResult, validate_registry
from feature_forge.types import EngineType


class FeatureStore:
    """Main entry point for feature-forge.

    Loads a feature registry from YAML files, validates it, and provides
    methods to retrieve features with point-in-time correctness.

    Usage::

        store = FeatureStore("./my_features")
        df = store.get_features_table(
            entity_df=labels_df,
            feature_views=["txn_features"],
        )
    """

    def __init__(
        self,
        repo_path: str | Path,
        engine: str | EngineType = EngineType.DUCKDB,
    ) -> None:
        self._repo_path = Path(repo_path).resolve()
        self._registry = load_registry(self._repo_path)

        # Engine from constructor takes priority, then YAML config
        engine_type = engine if engine != EngineType.DUCKDB else self._registry.engine
        self._engine: Engine = get_engine(engine_type)
        self._engine.connect()

    @property
    def registry(self) -> FeatureRegistry:
        return self._registry

    @property
    def entities(self) -> list[Any]:
        return self._registry.entities

    @property
    def sources(self) -> list[Any]:
        return self._registry.sources

    @property
    def feature_views(self) -> list[Any]:
        return self._registry.feature_views

    def validate(self) -> RegistryValidationResult:
        """Validate the feature registry for consistency and source accessibility."""
        return validate_registry(self._registry, str(self._repo_path))

    def get_features_table(
        self,
        feature_views: list[str],
        entity_df: pd.DataFrame | None = None,
        entity_ids: dict[str, list[Any]] | None = None,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        interval: str | None = None,
    ) -> pd.DataFrame:
        """Retrieve features with point-in-time correctness.

        Single method for training, inference, and historical backfill:

        - **Training**: pass ``entity_df`` with join keys + ``event_timestamp``
        - **Inference**: pass ``entity_ids``, features computed as of now
        - **Historical backfill**: pass ``entity_ids`` + ``start_date``/``end_date``/``interval``

        Args:
            feature_views: Names of feature views to retrieve.
            entity_df: DataFrame with entity join keys and ``event_timestamp`` column.
                Mutually exclusive with ``entity_ids``.
            entity_ids: Dict mapping join key names to lists of values.
                Example: ``{"customer_id": [101, 102, 103]}``
            start_date: Start date for historical backfill (default: now).
            end_date: End date for historical backfill (default: now).
            interval: Interval between points for backfill (e.g. "1d", "7d", "1h").
                Required when both ``start_date`` and ``end_date`` are provided.

        Returns:
            DataFrame with entity columns + all requested features.
        """
        if entity_df is not None and entity_ids is not None:
            raise FeatureForgeError(
                "Provide either 'entity_df' or 'entity_ids', not both"
            )
        if entity_df is None and entity_ids is None:
            raise FeatureForgeError(
                "Must provide either 'entity_df' or 'entity_ids'"
            )

        if entity_ids is not None:
            entity_df = self._build_entity_df(entity_ids, start_date, end_date, interval)

        assert entity_df is not None
        return retrieve_features(
            entity_df=entity_df,
            feature_view_names=feature_views,
            registry=self._registry,
            engine=self._engine,
            repo_path=str(self._repo_path),
        )

    def materialize(
        self,
        feature_views: list[str],
        entity_ids: dict[str, list[Any]],
        start_date: str | datetime,
        end_date: str | datetime,
        interval: str = "1d",
        output_path: str | Path | None = None,
    ) -> Path:
        """Materialize features to a Parquet file.

        Generates the full feature table for the given entities and date range,
        then writes it to Parquet.

        Args:
            feature_views: Names of feature views to materialize.
            entity_ids: Dict mapping join key names to lists of values.
            start_date: Start of the materialization window.
            end_date: End of the materialization window.
            interval: Time interval between points (default: "1d").
            output_path: Where to write the Parquet file. Defaults to
                ``.forge/materialized/<view_names>.parquet``.

        Returns:
            Path to the written Parquet file.
        """
        df = self.get_features_table(
            feature_views=feature_views,
            entity_ids=entity_ids,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )

        if output_path is None:
            forge_dir = self._repo_path / ".forge" / "materialized"
            forge_dir.mkdir(parents=True, exist_ok=True)
            view_label = "_".join(feature_views)
            output_path = forge_dir / f"{view_label}.parquet"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        df.to_parquet(output_path, index=False)
        return output_path

    def close(self) -> None:
        """Close the underlying engine connection."""
        self._engine.close()

    def __enter__(self) -> FeatureStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _build_entity_df(
        self,
        entity_ids: dict[str, list[Any]],
        start_date: str | datetime | None,
        end_date: str | datetime | None,
        interval: str | None,
    ) -> pd.DataFrame:
        """Build an entity DataFrame from entity_ids and optional date range."""
        # Build the base entity combinations
        keys = list(entity_ids.keys())
        values = list(entity_ids.values())

        # All value lists must have the same length
        lengths = {len(v) for v in values}
        if len(lengths) != 1:
            raise FeatureForgeError(
                f"All entity_ids value lists must have the same length, got {lengths}"
            )

        base_df = pd.DataFrame(entity_ids)

        if start_date is None and end_date is None:
            # Inference mode: single point at now
            base_df["event_timestamp"] = pd.Timestamp.now(tz=timezone.utc).tz_localize(None)
            return base_df

        # Historical backfill: generate date range
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date) if end_date else pd.Timestamp.now(tz=timezone.utc).tz_localize(None)

        if interval is None:
            raise FeatureForgeError(
                "'interval' is required when 'start_date' and 'end_date' are provided"
            )

        freq = self._parse_interval_to_freq(interval)
        timestamps = pd.date_range(start=start, end=end, freq=freq)

        if len(timestamps) == 0:
            raise FeatureForgeError(
                f"No timestamps generated for range {start} to {end} with interval '{interval}'"
            )

        # Cartesian product: entities x timestamps
        base_df["__key"] = 1
        ts_df = pd.DataFrame({"event_timestamp": timestamps, "__key": 1})
        result = base_df.merge(ts_df, on="__key").drop(columns=["__key"])

        return result

    @staticmethod
    def _parse_interval_to_freq(interval: str) -> str:
        """Convert interval string like '1d', '7d', '1h' to pandas freq string."""
        import re

        match = re.match(r"^(\d+)(d|h|m)$", interval)
        if not match:
            raise FeatureForgeError(
                f"Invalid interval '{interval}'. Use format like '1d', '7d', '1h', '30m'"
            )

        value, unit = match.group(1), match.group(2)
        freq_map = {"d": "D", "h": "h", "m": "min"}
        return f"{value}{freq_map[unit]}"
