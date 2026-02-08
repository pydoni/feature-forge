"""Feature retrieval orchestrator: coordinates PIT joins across multiple feature views."""

from __future__ import annotations

import pandas as pd

from feature_forge.backends.factory import get_backend
from feature_forge.engine.pit_join import build_pit_query
from feature_forge.engines.duckdb_engine import DuckDBEngine
from feature_forge.exceptions import EngineError
from feature_forge.registry.models import FeatureRegistry


def retrieve_features(
    entity_df: pd.DataFrame,
    feature_view_names: list[str],
    registry: FeatureRegistry,
    engine: DuckDBEngine,
    repo_path: str,
) -> pd.DataFrame:
    """Execute PIT joins for the requested feature views and merge results.

    Args:
        entity_df: DataFrame with entity join keys + event_timestamp column.
        feature_view_names: Names of feature views to retrieve.
        registry: The loaded feature registry.
        engine: The query engine to use.
        repo_path: Path to the feature repo (for resolving relative source paths).

    Returns:
        DataFrame with entity columns + all requested features.
    """
    if "event_timestamp" not in entity_df.columns:
        raise EngineError("entity_df must contain an 'event_timestamp' column")

    # Add a row index to preserve cardinality through merges with duplicate keys
    indexed_df = entity_df.copy()
    indexed_df["__row_idx"] = range(len(indexed_df))

    # Register the indexed entity_df in the engine
    engine.register_view("__entity_df", indexed_df)

    result_df = indexed_df.copy()

    for fv_name in feature_view_names:
        fv = registry.get_feature_view(fv_name)
        if fv is None:
            raise EngineError(f"Feature view '{fv_name}' not found in registry")

        source = registry.get_source(fv.source)
        if source is None:
            raise EngineError(f"Source '{fv.source}' not found in registry")

        entity = registry.get_entity(fv.entity)
        if entity is None:
            raise EngineError(f"Entity '{fv.entity}' not found in registry")

        # Validate entity keys exist in entity_df
        missing_keys = set(entity.join_keys) - set(entity_df.columns)
        if missing_keys:
            raise EngineError(
                f"entity_df is missing join keys for entity '{entity.name}': {sorted(missing_keys)}"
            )

        # Register the source in the engine via its backend
        source_view_name = f"__source_{source.name}"
        backend = get_backend(source.backend)
        backend.register_source(engine.conn, source, source_view_name, repo_path)

        # Resolve timestamp column
        source_ts_col = fv.timestamp_column or source.timestamp_column

        # Build and execute PIT query (includes __row_idx in output)
        sql = build_pit_query(
            entity_keys=entity.join_keys,
            entity_table="__entity_df",
            source_table=source_view_name,
            source_ts_col=source_ts_col,
            feature_view=fv,
        )

        fv_result = engine.execute_sql(sql)

        # Merge on __row_idx to preserve exact cardinality
        feature_cols = [f.name for f in fv.features]
        cols_to_merge = ["__row_idx"] + [c for c in feature_cols if c in fv_result.columns]

        result_df = result_df.merge(
            fv_result[cols_to_merge],
            on="__row_idx",
            how="left",
        )

    # Drop the internal row index
    result_df = result_df.drop(columns=["__row_idx"])
    return result_df
