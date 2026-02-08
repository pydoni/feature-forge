"""Point-in-time join SQL builder.

Generates DuckDB SQL for PIT-correct feature retrieval:
- Passthrough features: ASOF LEFT JOIN (latest value as of entity timestamp)
- Aggregation features: CTE per window group with time-bounded LEFT JOIN

The entity table must contain a __row_idx column to preserve row identity
through joins (handles duplicate entity key + timestamp combinations).
"""

from __future__ import annotations

from collections import defaultdict

from feature_forge.registry.models import Feature, FeatureView


def _entity_timestamp_col() -> str:
    return "event_timestamp"


def _build_agg_cte(
    cte_name: str,
    entity_keys: list[str],
    entity_table: str,
    source_table: str,
    source_ts_col: str,
    features: list[Feature],
    interval: str,
) -> str:
    """Build a CTE for a group of aggregation features sharing the same window."""
    agg_exprs: list[str] = []
    for f in features:
        assert f.aggregation is not None
        func = f.aggregation.function.value
        col = f.aggregation.column

        if func == "count_distinct":
            agg_exprs.append(f"COUNT(DISTINCT src.{col}) AS {f.name}")
        else:
            agg_exprs.append(f"{func.upper()}(src.{col}) AS {f.name}")

    key_join = " AND ".join(f"e.{k} = src.{k}" for k in entity_keys)
    ets = _entity_timestamp_col()

    return (
        f"{cte_name} AS (\n"
        f"  SELECT\n"
        f"    e.__row_idx,\n"
        f"    {',\n    '.join(agg_exprs)}\n"
        f"  FROM {entity_table} e\n"
        f"  LEFT JOIN {source_table} src\n"
        f"    ON {key_join}\n"
        f"    AND src.{source_ts_col} <= e.{ets}\n"
        f"    AND src.{source_ts_col} > e.{ets} - INTERVAL '{interval}'\n"
        f"  GROUP BY e.__row_idx\n"
        f")"
    )


def build_pit_query(
    entity_keys: list[str],
    entity_table: str,
    source_table: str,
    source_ts_col: str,
    feature_view: FeatureView,
) -> str:
    """Build the complete PIT join SQL for a single feature view.

    Returns a SQL query that joins the entity table with the source,
    producing one row per entity row with all requested features.
    The entity table must have a __row_idx column.
    """
    passthrough_features = [f for f in feature_view.features if f.column is not None]
    agg_features = [f for f in feature_view.features if f.aggregation is not None]

    # Group aggregation features by window
    window_groups: dict[str, list[Feature]] = defaultdict(list)
    for f in agg_features:
        assert f.aggregation is not None
        window_groups[f.aggregation.window_to_interval()].append(f)

    ets = _entity_timestamp_col()

    ctes: list[str] = []
    join_tables: list[str] = []
    select_parts: list[str] = [
        f"entity.__row_idx",
        *(f"entity.{k}" for k in entity_keys),
        f"entity.{ets}",
    ]

    # Build CTEs for aggregation window groups
    for i, (interval, features) in enumerate(sorted(window_groups.items())):
        cte_name = f"agg_{i}"
        ctes.append(
            _build_agg_cte(
                cte_name=cte_name,
                entity_keys=entity_keys,
                entity_table="entity",
                source_table=source_table,
                source_ts_col=source_ts_col,
                features=features,
                interval=interval,
            )
        )
        join_tables.append(cte_name)
        for f in features:
            select_parts.append(f"{cte_name}.{f.name}")

    # Passthrough features via ASOF JOIN
    asof_alias = None
    if passthrough_features:
        asof_alias = "passthrough"
        for f in passthrough_features:
            select_parts.append(f"{asof_alias}.{f.name}")

    # Compose final query
    parts: list[str] = []

    # WITH clause
    if ctes:
        parts.append(f"WITH entity AS (\n  SELECT * FROM {entity_table}\n),")
        parts.append(",\n".join(ctes))
    else:
        parts.append(f"WITH entity AS (\n  SELECT * FROM {entity_table}\n)")

    # SELECT
    parts.append(f"SELECT\n  {',\n  '.join(select_parts)}")
    parts.append("FROM entity")

    # JOIN aggregation CTEs on __row_idx
    for cte_name in join_tables:
        parts.append(f"LEFT JOIN {cte_name} ON entity.__row_idx = {cte_name}.__row_idx")

    # ASOF JOIN for passthrough
    if passthrough_features and asof_alias:
        asof_select = ", ".join(
            f"src.{f.column} AS {f.name}" for f in passthrough_features
        )
        parts.append(
            f"ASOF LEFT JOIN (\n"
            f"  SELECT {', '.join(entity_keys)}, {source_ts_col}, {asof_select}\n"
            f"  FROM {source_table} src\n"
            f") AS {asof_alias}\n"
            f"  ON {' AND '.join(f'entity.{k} = {asof_alias}.{k}' for k in entity_keys)}\n"
            f"  AND entity.{ets} >= {asof_alias}.{source_ts_col}"
        )

    return "\n".join(parts)
