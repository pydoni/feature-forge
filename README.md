# feature-forge

Lightweight feature store for small and medium ML teams. Define features in YAML, get point-in-time correct data with one method call. No infrastructure required.

## Install

```bash
pip install fforge
```

With optional backends:

```bash
pip install fforge[databricks]   # Databricks Unity Catalog
pip install fforge[spark]        # PySpark engine
pip install fforge[all]          # Everything
```

## What it does

- **Point-in-time correct joins**: for each row in your data, features are computed using only past information. No data leakage.
- **YAML-based feature definitions**: entities, sources, and features are declared in version-controlled YAML files.
- **Multiple data sources**: Parquet (local), S3/GCS/Azure, SQLite/PostgreSQL, Databricks Unity Catalog.
- **Two query engines**: DuckDB (default, zero-config) or PySpark (for Spark clusters).
- **One method for everything**: `get_features_table()` handles training, inference, and historical backfill.
- **CLI included**: init, validate, list, describe, materialize.

## Quickstart

**1. Initialize**

```bash
feature-forge init my_features/
```

**2. Define** (edit the generated YAML files)

```yaml
# entities.yml
entities:
  - name: customer
    join_keys: [customer_id]
```

```yaml
# sources.yml
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

```yaml
# features.yml
feature_views:
  - name: customer_features
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

**3. Validate**

```bash
feature-forge validate --repo my_features/
```

**4. Use**

```python
from feature_forge import FeatureStore
import pandas as pd

store = FeatureStore("my_features/")

labels = pd.DataFrame({
    "customer_id": [101, 102],
    "event_timestamp": pd.to_datetime(["2025-03-15", "2025-03-20"]),
    "is_fraud": [1, 0],
})

df = store.get_features_table(
    entity_df=labels,
    feature_views=["customer_features"],
)
# customer_id | event_timestamp | is_fraud | txn_count_7d | avg_amount_30d
# Each row uses ONLY data before its timestamp
```

## Example: training, inference, and backfill

```python
from feature_forge import FeatureStore

store = FeatureStore("my_features/")

# TRAINING: pass labeled data with historical timestamps
training_df = store.get_features_table(
    entity_df=labels_df,
    feature_views=["customer_features"],
)

# INFERENCE: pass entity IDs, features computed as of now
inference_df = store.get_features_table(
    entity_ids={"customer_id": [101, 102, 103]},
    feature_views=["customer_features"],
)

# BACKFILL: entity IDs + date range for historical scoring
backfill_df = store.get_features_table(
    entity_ids={"customer_id": [101, 102]},
    feature_views=["customer_features"],
    start_date="2025-01-01",
    end_date="2025-06-01",
    interval="1d",
)

store.close()
```

Same method, same PIT guarantees. The behavior changes based on which parameters you pass.

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/01-getting-started.md) | 5-minute setup |
| [Defining Features](docs/02-defining-features.md) | Entities, sources, aggregation vs passthrough |
| [Retrieving Features](docs/03-retrieving-features.md) | Training, inference, backfill modes |
| [Backends](docs/04-backends.md) | Parquet, S3, SQL, Databricks configuration |
| [Engines](docs/05-engines.md) | DuckDB vs PySpark |
| [Materialization](docs/06-materialization.md) | Pre-compute and save to Parquet |
| [CLI Reference](docs/07-cli-reference.md) | All commands and flags |

## Development

```bash
git clone https://github.com/pydoni/feature-forge.git
cd feature-forge
uv sync --extra dev
uv run pytest
```

## License

Apache 2.0
