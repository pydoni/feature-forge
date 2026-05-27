# Getting Started

This guide walks you through your first feature-forge project in under 5 minutes.

## Prerequisites

- Python 3.10+
- A dataset in Parquet format (or any supported backend)

## 1. Install

```bash
pip install feature-forge
```

## 2. Initialize a feature repo

```bash
feature-forge init my_features/
cd my_features/
```

This creates three YAML files:

```
my_features/
  entities.yml     # who your features describe
  sources.yml      # where raw data lives
  features.yml     # what to compute
```

## 3. Edit the YAML files

Suppose you have a `data/transactions.parquet` file with columns `customer_id`, `amount`, and `event_timestamp`.

**entities.yml**
```yaml
entities:
  - name: customer
    join_keys: [customer_id]
```

**sources.yml**
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

**features.yml**
```yaml
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

## 4. Validate

```bash
feature-forge validate
```

If everything is correct, you'll see `Registry is valid.`

## 5. Get features in Python

```python
from feature_forge import FeatureStore
import pandas as pd

store = FeatureStore("my_features/")

# Your labeled data
labels = pd.DataFrame({
    "customer_id": [101, 102],
    "event_timestamp": pd.to_datetime(["2025-03-15", "2025-03-20"]),
    "is_fraud": [1, 0],
})

# Get features (point-in-time correct)
df = store.get_features_table(
    entity_df=labels,
    feature_views=["customer_features"],
)

print(df)
# customer_id | event_timestamp | is_fraud | txn_count_7d | avg_amount_30d
```

Each row uses **only data available before its timestamp**. No data leakage.

## What's next

- [Defining Features](02-defining-features.md): learn about entities, sources, and feature types
- [Retrieving Features](03-retrieving-features.md): training, inference, and backfill modes
- [Backends](04-backends.md): connect to S3, SQL databases, or Databricks
