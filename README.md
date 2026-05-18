# feature-forge

Lightweight feature store for small and medium ML teams. Define features in YAML, get point-in-time correct training data with one method call. No infrastructure required.

```python
from feature_forge import FeatureStore

store = FeatureStore("./my_features")

# Training: pass labels with historical timestamps
training_df = store.get_features_table(
    entity_df=labels_df,
    feature_views=["customer_txn_features"],
)

# Inference: pass entity IDs, features computed as of now
inference_df = store.get_features_table(
    entity_ids={"customer_id": [101, 102]},
    feature_views=["customer_txn_features"],
)

# Historical backfill: entity IDs + date range
backfill_df = store.get_features_table(
    entity_ids={"customer_id": [101, 102]},
    feature_views=["customer_txn_features"],
    start_date="2025-01-01",
    end_date="2025-06-01",
    interval="1d",
)
```

## Why feature-forge?

Most feature stores (Feast, Tecton, Hopsworks) are built for large organizations with dedicated infrastructure teams. If you're a small/medium team that just needs:

- **Point-in-time correct joins** without data leakage
- **Declarative feature definitions** in version-controlled YAML
- **Multiple data sources** (Parquet, S3, SQL databases, Databricks)
- **Zero infrastructure** to set up

Then feature-forge is for you. It runs entirely on your laptop using DuckDB, or scales to Spark clusters when needed.

## Installation

```bash
pip install feature-forge
```

With optional backends:

```bash
pip install feature-forge[databricks]   # Databricks SQL Warehouse support
pip install feature-forge[spark]        # PySpark engine
pip install feature-forge[all]          # Everything
```

## Quickstart

### 1. Initialize a feature repo

```bash
feature-forge init my_features/
```

This creates three YAML files:

### 2. Define your entities, sources, and features

**entities.yml** - who your features describe:

```yaml
entities:
  - name: customer
    join_keys: [customer_id]
```

**sources.yml** - where raw data lives:

```yaml
sources:
  - name: transactions
    backend: parquet
    path: data/transactions.parquet
    entity: customer
    timestamp_column: event_timestamp
    columns:
      - { name: customer_id, dtype: int64 }
      - { name: amount, dtype: float64 }
      - { name: event_timestamp, dtype: timestamp }
```

**features.yml** - what to compute:

```yaml
feature_views:
  - name: customer_txn_features
    entity: customer
    source: transactions
    features:
      - name: txn_count_7d
        dtype: int64
        aggregation: { function: count, column: amount, window: 7d }

      - name: avg_amount_30d
        dtype: float64
        aggregation: { function: avg, column: amount, window: 30d }
```

### 3. Validate

```bash
feature-forge validate --repo my_features/
```

### 4. Get features

```python
from feature_forge import FeatureStore
import pandas as pd

store = FeatureStore("my_features/")

labels = pd.DataFrame({
    "customer_id": [101, 102],
    "event_timestamp": pd.to_datetime(["2025-03-15", "2025-03-20"]),
    "is_fraud": [1, 0],
})

training_df = store.get_features_table(
    entity_df=labels,
    feature_views=["customer_txn_features"],
)
# customer_id | event_timestamp | is_fraud | txn_count_7d | avg_amount_30d
# Each row uses ONLY data before its timestamp. Zero leakage.
```

## Features

### Point-in-time correct joins

The core guarantee: for each row in your entity DataFrame, features are computed using **only data available at that row's timestamp**. This prevents data leakage in training and ensures consistency between training and inference.

DuckDB's native `ASOF JOIN` powers this for the default engine. The Spark engine uses window functions to achieve the same result.

### Two feature modes

**Passthrough** - latest value as of the entity timestamp:

```yaml
features:
  - name: customer_age
    dtype: int32
    column: age  # picks the most recent 'age' value
```

**Aggregation** - windowed computation:

```yaml
features:
  - name: txn_count_7d
    dtype: int64
    aggregation:
      function: count    # count, sum, avg, min, max, count_distinct
      column: amount
      window: 7d         # 7d, 30d, 24h, 60m
```

### Multiple backends

| Backend | Config | Use case |
|---------|--------|----------|
| Parquet | `backend: parquet`, `path: data/file.parquet` | Local files (default) |
| S3/GCS/Azure | `backend: s3`, `uri: s3://bucket/path/*.parquet` | Cloud object storage |
| SQLite/PostgreSQL | `backend: sql`, `connection_string: ...` | SQL databases |
| Databricks | `backend: databricks`, `table: catalog.schema.table` | Unity Catalog tables |

### Two engines

| Engine | Best for | PIT join method |
|--------|----------|-----------------|
| DuckDB (default) | Local, up to ~100GB | Native ASOF JOIN |
| PySpark | Databricks, Spark clusters | Window functions |

```python
# Use Spark engine
store = FeatureStore("my_features/", engine="spark")
```

### Materialization

Save pre-computed features to Parquet:

```python
store.materialize(
    feature_views=["customer_txn_features"],
    entity_ids={"customer_id": [101, 102, 103]},
    start_date="2025-01-01",
    end_date="2025-06-01",
    interval="1d",
)
# Writes to .forge/materialized/customer_txn_features.parquet
```

## CLI Reference

```
feature-forge init [PATH]              Initialize a feature repo with template YAML
feature-forge validate [--repo PATH]   Validate registry (schema, refs, sources)
feature-forge list entities|sources|features [--repo PATH]
feature-forge describe FEATURE_VIEW [--repo PATH]
feature-forge materialize VIEW --start DATE --end DATE \
    --entity-key KEY --entity-values 1,2,3 [--engine spark] [--repo PATH]
```

## API Reference

### `FeatureStore(repo_path, engine="duckdb")`

Main entry point. Loads YAML registry and connects to the engine.

### `store.get_features_table(...)`

Single method for all use cases:

| Parameter | Training | Inference | Backfill |
|-----------|----------|-----------|----------|
| `entity_df` | DataFrame with keys + timestamps | - | - |
| `entity_ids` | - | `{"key": [values]}` | `{"key": [values]}` |
| `start_date` | - | - | `"2025-01-01"` |
| `end_date` | - | - | `"2025-06-01"` |
| `interval` | - | - | `"1d"` |
| `feature_views` | Required | Required | Required |

### `store.validate()`

Returns a `RegistryValidationResult` with any issues found.

### `store.materialize(...)`

Computes features and writes to Parquet. Returns the output path.

## Development

```bash
git clone https://github.com/pydoni/feature-forge.git
cd feature-forge
uv sync --extra dev --extra spark
uv run pytest
uv run ruff check src/ tests/
```

## License

Apache 2.0
