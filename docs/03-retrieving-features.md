# Retrieving Features

feature-forge provides a single method, `get_features_table()`, that handles three use cases: training, inference, and historical backfill. The method signature is the same; the behavior changes based on which parameters you pass.

## Setup

```python
from feature_forge import FeatureStore

store = FeatureStore("my_features/")
```

## Mode 1: Training

Pass an `entity_df` with your labeled data. Each row must have the entity join keys and an `event_timestamp` column.

```python
import pandas as pd

labels = pd.DataFrame({
    "customer_id": [101, 102, 103, 101],
    "event_timestamp": pd.to_datetime([
        "2025-01-15", "2025-01-20", "2025-01-25", "2025-02-05"
    ]),
    "is_fraud": [0, 0, 1, 0],   # your labels (preserved in output)
})

training_df = store.get_features_table(
    entity_df=labels,
    feature_views=["txn_features", "profile_features"],
)
```

**What happens:** for each row, features are computed using only data with timestamps **before** that row's `event_timestamp`. Your original columns (like `is_fraud`) are preserved in the output.

**Output:**

| customer_id | event_timestamp | is_fraud | txn_count_7d | avg_amount_30d | customer_age |
|---|---|---|---|---|---|
| 101 | 2025-01-15 | 0 | 2 | 150.0 | 34 |
| 102 | 2025-01-20 | 0 | 1 | 300.0 | 28 |
| 103 | 2025-01-25 | 1 | 3 | 95.0 | 45 |
| 101 | 2025-02-05 | 0 | 1 | 130.0 | 34 |

Notice customer 101 appears twice with different timestamps, and gets different feature values each time. This is point-in-time correctness.

## Mode 2: Inference

Pass `entity_ids` without date parameters. Features are computed as of the current timestamp.

```python
inference_df = store.get_features_table(
    entity_ids={"customer_id": [101, 102, 103]},
    feature_views=["txn_features"],
)
```

**What happens:** feature-forge generates an internal entity DataFrame with `event_timestamp = now()` for each entity, then runs the same PIT join. This is what you'd use in production to get features for model scoring.

## Mode 3: Historical backfill

Pass `entity_ids` with `start_date`, `end_date`, and `interval`. feature-forge generates a cartesian product of entities and timestamps, then computes features for each combination.

```python
backfill_df = store.get_features_table(
    entity_ids={"customer_id": [101, 102]},
    feature_views=["txn_features"],
    start_date="2025-01-01",
    end_date="2025-01-10",
    interval="1d",
)
```

**What happens:** generates 2 customers x 10 days = 20 rows, each with features computed as of that date. Useful for:
- Retroactive scoring (generate predictions for past dates)
- Model monitoring (compare feature distributions over time)
- Backtesting strategies

**Available intervals:** `1d`, `7d`, `30d`, `1h`, `60m`, etc. Same format as feature windows.

## Combining multiple feature views

You can request features from different sources in a single call:

```python
df = store.get_features_table(
    entity_df=labels,
    feature_views=["txn_features", "profile_features", "event_features"],
)
```

Each feature view runs its own PIT join against its source, and the results are merged together on the entity keys. You can mix backends (e.g., one view from Parquet, another from Databricks).

## How the PIT join works

For each row in your entity DataFrame:

1. **Aggregation features** (e.g., `count` with `window: 7d`): filters the source to records where `source_timestamp > entity_timestamp - 7 days AND source_timestamp <= entity_timestamp`, then computes the aggregate.

2. **Passthrough features** (e.g., `column: age`): finds the most recent source record where `source_timestamp <= entity_timestamp` and takes the column value.

The join key (e.g., `customer_id`) ensures each entity only sees its own data. The timestamp filter ensures no future data is used.

## Composite entity keys

If your entity has multiple join keys, your entity DataFrame must contain all of them:

```python
entity_df = pd.DataFrame({
    "customer_id": [101, 101],
    "product_id": ["A", "B"],
    "event_timestamp": pd.to_datetime(["2025-03-15", "2025-03-15"]),
})

df = store.get_features_table(
    entity_df=entity_df,
    feature_views=["customer_product_features"],
)
```

## Error handling

The method raises `FeatureForgeError` (or subclasses) when:
- Both `entity_df` and `entity_ids` are provided (or neither)
- `entity_df` is missing the `event_timestamp` column
- A requested feature view doesn't exist in the registry
- Entity join keys are missing from the DataFrame
- Backfill mode is used without `interval`

## Closing the store

`FeatureStore` holds an engine connection. Close it when done:

```python
store.close()
```

Or use a context manager:

```python
with FeatureStore("my_features/") as store:
    df = store.get_features_table(...)
# connection closed automatically
```
