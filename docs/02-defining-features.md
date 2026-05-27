# Defining Features

Features in feature-forge are defined declaratively in YAML files. A feature repo has three types of definitions: **entities**, **sources**, and **feature views**.

## Entities

An entity is the subject of your features. It defines the **join keys** that identify a unique record.

```yaml
# entities.yml
entities:
  - name: customer
    join_keys: [customer_id]
    description: "A retail customer"
```

### Composite keys

Entities can have multiple join keys for compound identification:

```yaml
entities:
  - name: customer_product
    join_keys:
      - customer_id
      - product_id
    description: "Customer-product pair for recommendation features"
```

When you retrieve features, your entity DataFrame must contain all join key columns.

## Sources

A source tells feature-forge where to find raw data and how it's structured.

```yaml
# sources.yml
sources:
  - name: transactions
    backend: parquet                    # parquet, s3, sql, or databricks
    path: data/transactions.parquet    # backend-specific config
    entity: customer                   # which entity this data relates to
    timestamp_column: event_timestamp  # column used for point-in-time filtering
    columns:
      - { name: customer_id, dtype: int64 }
      - { name: amount, dtype: float64 }
      - { name: event_timestamp, dtype: timestamp }
      - { name: merchant_id, dtype: varchar }
```

**Required fields:**
- `name`: unique identifier for this source
- `backend`: one of `parquet`, `s3`, `sql`, `databricks`
- `entity`: which entity this source belongs to
- `timestamp_column`: the column that represents when each record occurred
- `columns`: declared schema with name and dtype

**Supported dtypes:** `int32`, `int64`, `float32`, `float64`, `varchar`, `boolean`, `timestamp`, `date`

See [Backends](04-backends.md) for backend-specific configuration.

## Feature Views

A feature view groups features that are computed from a single source.

```yaml
# features.yml
feature_views:
  - name: customer_txn_features
    entity: customer
    source: transactions
    features:
      - name: txn_count_7d
        dtype: int64
        description: "Transactions in the last 7 days"
        aggregation:
          function: count
          column: amount
          window: 7d
```

### Feature modes

Each feature must be one of two modes:

#### Aggregation

Computes a value over a time window. Only data within the window and before the entity timestamp is used.

```yaml
- name: avg_amount_30d
  dtype: float64
  aggregation:
    function: avg       # what to compute
    column: amount      # which source column
    window: 30d         # time window
```

**Available functions:**

| Function | Output | Description |
|----------|--------|-------------|
| `count` | int64 | Number of records in the window |
| `sum` | same as column | Sum of values |
| `avg` | float64 | Mean of values |
| `min` | same as column | Minimum value |
| `max` | same as column | Maximum value |
| `count_distinct` | int64 | Number of unique values |

**Window format:** `<number><unit>` where unit is `d` (days), `h` (hours), or `m` (minutes).

Examples: `7d`, `30d`, `24h`, `60m`, `365d`

**What happens when there's no data in the window:**
- `count` and `count_distinct` return `0`
- `sum`, `avg`, `min`, `max` return `null`

#### Passthrough

Picks the most recent value from the source that occurred at or before the entity timestamp. No aggregation, no window.

```yaml
- name: customer_age
  dtype: int32
  column: age       # source column name
```

Use passthrough for slowly-changing data like demographics, account status, or segment labels.

If the source has multiple records for the same entity with different timestamps, passthrough picks the latest one that is still in the past relative to the query point:

| customer_id | age | updated_at |
|---|---|---|
| 101 | 34 | 2025-01-01 |
| 101 | 35 | 2025-07-01 |

Query at 2025-03-15 returns `age = 34`. Query at 2025-08-01 returns `age = 35`.

### Multiple feature views

You can define multiple feature views, even from different sources:

```yaml
feature_views:
  - name: txn_features
    entity: customer
    source: transactions
    features: [...]

  - name: profile_features
    entity: customer
    source: profiles
    features: [...]
```

When you retrieve features, you can request any combination of views and they'll be merged into a single DataFrame.

## Validation

Run `feature-forge validate` (or `store.validate()` in Python) to check:

1. No duplicate entity, source, or feature view names
2. All source references point to existing entities
3. All feature view references point to existing entities and sources
4. Entity consistency between feature view and its source
5. Feature columns exist in the declared source schema
6. `count`/`count_distinct` features have `dtype: int64`
7. Backend-specific checks (file exists, credentials available, etc.)
