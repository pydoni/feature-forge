# Materialization

Materialization pre-computes features and saves them to Parquet files. This is useful for:

- **Production caching:** pre-compute features once, read them quickly at inference time
- **Data sharing:** export feature tables for other teams or systems
- **Auditing:** snapshot feature values at a specific point in time

## Python API

```python
from feature_forge import FeatureStore

store = FeatureStore("my_features/")

output_path = store.materialize(
    feature_views=["customer_txn_features"],
    entity_ids={"customer_id": [101, 102, 103]},
    start_date="2025-01-01",
    end_date="2025-06-01",
    interval="1d",
)

print(f"Saved to: {output_path}")
```

**Parameters:**
- `feature_views`: which feature views to include
- `entity_ids`: which entities to compute features for
- `start_date` / `end_date`: date range
- `interval`: time step (e.g., `1d`, `7d`)
- `output_path` (optional): where to save the Parquet file

**Default output path:** `<repo>/.forge/materialized/<view_names>.parquet`

The output is a standard Parquet file that can be read by pandas, Spark, DuckDB, or any other tool.

## CLI

```bash
feature-forge materialize customer_txn_features \
    --start 2025-01-01 \
    --end 2025-06-01 \
    --entity-key customer_id \
    --entity-values 101,102,103 \
    --interval 1d \
    --output output/features.parquet \
    --repo my_features/
```

## Reading materialized features

Materialized Parquet files are standard DataFrames:

```python
import pandas as pd

df = pd.read_parquet(".forge/materialized/customer_txn_features.parquet")
```

## Materialization vs. live computation

| | `get_features_table()` | `materialize()` |
|---|---|---|
| **When to use** | Interactive development, real-time inference | Batch jobs, caching, exports |
| **Output** | In-memory DataFrame | Parquet file on disk |
| **Freshness** | Always up to date | Snapshot at materialization time |
| **Speed for repeated queries** | Recomputes each time | Read from disk |
