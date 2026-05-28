# Backends

Backends define where feature-forge reads source data from. All backends register data as views in the query engine (DuckDB or Spark), so the feature computation logic is the same regardless of where the data lives.

## Parquet (default)

Local Parquet files. No additional dependencies.

```yaml
sources:
  - name: transactions
    backend: parquet
    path: data/transactions.parquet    # relative to feature repo, or absolute
    entity: customer
    timestamp_column: event_timestamp
    columns:
      - { name: customer_id, dtype: int64 }
      - { name: amount, dtype: float64 }
      - { name: event_timestamp, dtype: timestamp }
```

**Validation:** checks that the file exists and contains the declared columns.

Paths can be relative (resolved from the feature repo directory) or absolute.

## S3 / GCS / Azure Blob

Cloud object storage via DuckDB's httpfs extension. No additional pip dependencies.

```yaml
sources:
  - name: logs
    backend: s3
    uri: s3://my-bucket/data/logs/*.parquet    # supports glob patterns
    entity: customer
    timestamp_column: log_timestamp
    columns: [...]
```

**Supported URI schemes:**
- `s3://` for AWS S3
- `gs://` or `gcs://` for Google Cloud Storage
- `az://` or `abfss://` for Azure Blob Storage

**Authentication** is resolved from environment variables:

| Cloud | Variables |
|-------|-----------|
| AWS | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_SESSION_TOKEN` |
| GCS | Default credentials (gcloud auth) |
| Azure | `AZURE_STORAGE_CONNECTION_STRING` |

## SQL (SQLite / PostgreSQL)

SQL databases via DuckDB's ATTACH mechanism.

```yaml
sources:
  # SQLite
  - name: events
    backend: sql
    connection_string: data/events.db           # path to .db file
    query: "SELECT * FROM __sqldb_events.events" # query against attached db
    entity: customer
    timestamp_column: created_at
    columns: [...]

  # PostgreSQL
  - name: crm_data
    backend: sql
    connection_string: "host=localhost dbname=crm user=readonly"
    query: "SELECT * FROM __sqldb_crm_data.customers"
    entity: customer
    timestamp_column: updated_at
    columns: [...]
```

**Database type** is auto-detected from the connection string:
- Files ending in `.db`, `.sqlite`, `.sqlite3` are treated as SQLite
- Strings containing `host=`, `postgresql://`, or `postgres://` are treated as PostgreSQL

**Important:** the `query` must reference the attached database using the alias `__sqldb_<source_name>`. For example, if your source is named `events`, the attached DB is accessible as `__sqldb_events`.

Alternatively, use `table` instead of `query`:

```yaml
  - name: events
    backend: sql
    connection_string: data/events.db
    table: events                        # shorthand for SELECT * FROM __sqldb_events.events
    entity: customer
    timestamp_column: created_at
    columns: [...]
```

**Validation:** for SQLite, checks that the database file exists. For PostgreSQL, validates the connection string format.

## Databricks

Unity Catalog tables via SQL Warehouse or native Spark.

```bash
pip install fforge[databricks]
```

```yaml
sources:
  - name: prescriptions
    backend: databricks
    table: catalog.schema.prescriptions         # Unity Catalog path
    host: adb-123.azuredatabricks.net           # or DATABRICKS_HOST env var
    warehouse_id: abc123def                     # or DATABRICKS_WAREHOUSE_ID env var
    entity: doctor
    timestamp_column: dt_prescricao
    columns:
      - { name: doctor_id, dtype: int64 }
      - { name: units, dtype: int64 }
      - { name: dt_prescricao, dtype: timestamp }
```

**Two modes** (auto-detected):

| Mode | When | How it works |
|------|------|--------------|
| SQL Warehouse | Running outside Databricks (laptop, CI) | Uses `databricks-sql-connector` to query via SQL Warehouse, returns Arrow |
| Native Spark | Running inside a Databricks notebook | Detects `DATABRICKS_RUNTIME_VERSION` env var, uses `spark.sql()` directly |

**Authentication:**
- `host`: from YAML config or `DATABRICKS_HOST` env var
- `warehouse_id`: from YAML config or `DATABRICKS_WAREHOUSE_ID` env var
- Token: always from `DATABRICKS_TOKEN` env var (never in YAML)

Inside Databricks notebooks, no token is needed since authentication is handled by the runtime.

**Custom queries:** use `query` instead of (or alongside) `table`:

```yaml
  - name: filtered_prescriptions
    backend: databricks
    table: catalog.schema.prescriptions
    query: "SELECT * FROM catalog.schema.prescriptions WHERE country = 'BR'"
    entity: doctor
    timestamp_column: dt_prescricao
    columns: [...]
```

## Mixing backends

You can use different backends in the same feature repo. Each source is independent:

```yaml
sources:
  - name: transactions
    backend: parquet
    path: data/transactions.parquet
    entity: customer
    timestamp_column: event_timestamp
    columns: [...]

  - name: profiles
    backend: sql
    connection_string: data/crm.db
    query: "SELECT * FROM __sqldb_profiles.customers"
    entity: customer
    timestamp_column: updated_at
    columns: [...]

  - name: events
    backend: databricks
    table: catalog.marketing.events
    entity: customer
    timestamp_column: event_date
    columns: [...]
```

```python
# One call, three backends, one result
df = store.get_features_table(
    entity_df=labels,
    feature_views=["txn_features", "profile_features", "event_features"],
)
```
