"""Point-in-time join SQL builder for Spark SQL.

Spark SQL does not support ASOF JOIN, so we use window functions:
- Passthrough features: ROW_NUMBER() OVER (PARTITION BY keys ORDER BY ts DESC) + filter rn=1
- Aggregation features: time-bounded LEFT JOIN + GROUP BY (same as DuckDB, adjusted INTERVAL)

The entity table must contain a __row_idx column to preserve row identity.
"""

from __future__ import annotations

from collections import defaultdict

from feature_forge.registry.models import Feature, FeatureView

_AGG_SEP = ",\n    "
_SELECT_SEP = ",\n  "


def _entity_timestamp_col() -> str:
    return "event_timestamp"


def _window_to_spark_interval(interval: str) -> str:
    """Convert '7 days' to 'INTERVAL 7 DAY' for Spark SQL."""
    parts = interval.split()
    value = parts[0]
    unit = parts[1].upper().rstrip("S")  # "days" -> "DAY"
    return f"INTERVAL {value} {unit}"


def _build_passthrough_cte(
    cte_name: str,
    entity_keys: list[str],
    entity_table: str,
    source_table: str,
    source_ts_col: str,
    features: list[Feature],
) -> str:
    """Build a CTE for passthrough features using ROW_NUMBER window function."""
    ets = _entity_timestamp_col()
    key_join = " AND ".join(f"e.{k} = src.{k}" for k in entity_keys)
    feature_cols = ", ".join(f"src.{f.column} AS {f.name}" for f in features)

    return (
        f"{cte_name} AS (\n"
        f"  SELECT\n"
        f"    e.__row_idx,\n"
        f"    {feature_cols},\n"
        f"    ROW_NUMBER() OVER (\n"
        f"      PARTITION BY e.__row_idx\n"
        f"      ORDER BY src.{source_ts_col} DESC NULLS LAST\n"
        f"    ) AS __rn\n"
        f"  FROM {entity_table} e\n"
        f"  LEFT JOIN {source_table} src\n"
        f"    ON {key_join}\n"
        f"    AND src.{source_ts_col} <= e.{ets}\n"
        f"),\n"
        f"{cte_name}_latest AS (\n"
        f"  SELECT __row_idx, {', '.join(f.name for f in features)}\n"
        f"  FROM {cte_name}\n"
        f"  WHERE __rn = 1\n"
        f")"
    )


def _build_agg_cte(
    cte_name: str,
    entity_keys: list[str],
    entity_table: str,
    source_table: str,
    source_ts_col: str,
    features: list[Feature],
    interval: str,
) -> str:
    """Build a CTE for aggregation features with a time window."""
    agg_exprs: list[str] = []
    for f in features:
        if f.aggregation is None:
            raise ValueError(f"Feature '{f.name}' has no aggregation defined")
        func = f.aggregation.function.value
        col = f.aggregation.column

        if func == "count_distinct":
            agg_exprs.append(f"COUNT(DISTINCT src.{col}) AS {f.name}")
        else:
            agg_exprs.append(f"{func.upper()}(src.{col}) AS {f.name}")

    key_join = " AND ".join(f"e.{k} = src.{k}" for k in entity_keys)
    ets = _entity_timestamp_col()
    spark_interval = _window_to_spark_interval(interval)

    return (
        f"{cte_name} AS (\n"
        f"  SELECT\n"
        f"    e.__row_idx,\n"
        f"    {_AGG_SEP.join(agg_exprs)}\n"
        f"  FROM {entity_table} e\n"
        f"  LEFT JOIN {source_table} src\n"
        f"    ON {key_join}\n"
        f"    AND src.{source_ts_col} <= e.{ets}\n"
        f"    AND src.{source_ts_col} > e.{ets} - {spark_interval}\n"
        f"  GROUP BY e.__row_idx\n"
        f")"
    )


def build_spark_pit_query(
    entity_keys: list[str],
    entity_table: str,
    source_table: str,
    source_ts_col: str,
    feature_view: FeatureView,
) -> str:
    """Build the complete PIT join SQL for Spark SQL.

    Uses window functions for passthrough (ROW_NUMBER) and time-bounded
    LEFT JOIN + GROUP BY for aggregations.
    """
    passthrough_features = [f for f in feature_view.features if f.column is not None]
    agg_features = [f for f in feature_view.features if f.aggregation is not None]

    # Group aggregation features by window
    window_groups: dict[str, list[Feature]] = defaultdict(list)
    for f in agg_features:
        if f.aggregation is None:
            raise ValueError(f"Feature '{f.name}' has no aggregation defined")
        window_groups[f.aggregation.window_to_interval()].append(f)

    ets = _entity_timestamp_col()

    ctes: list[str] = []
    join_tables: list[str] = []
    select_parts: list[str] = [
        "entity.__row_idx",
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

    # Build CTE for passthrough features
    passthrough_join_name = None
    if passthrough_features:
        passthrough_join_name = "pt_latest"
        ctes.append(
            _build_passthrough_cte(
                cte_name="pt",
                entity_keys=entity_keys,
                entity_table="entity",
                source_table=source_table,
                source_ts_col=source_ts_col,
                features=passthrough_features,
            )
        )
        join_tables.append(passthrough_join_name)
        for f in passthrough_features:
            select_parts.append(f"{passthrough_join_name}.{f.name}")

    # Compose final query
    parts: list[str] = []

    # WITH clause
    entity_cte = f"entity AS (\n  SELECT * FROM {entity_table}\n)"
    if ctes:
        parts.append(f"WITH {entity_cte},")
        parts.append(",\n".join(ctes))
    else:
        parts.append(f"WITH {entity_cte}")

    # SELECT
    parts.append(f"SELECT\n  {_SELECT_SEP.join(select_parts)}")
    parts.append("FROM entity")

    # JOIN CTEs on __row_idx
    for table_name in join_tables:
        parts.append(
            f"LEFT JOIN {table_name} ON entity.__row_idx = {table_name}.__row_idx"
        )

    return "\n".join(parts)
