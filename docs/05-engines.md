# Engines

Engines determine where the feature computation SQL runs. feature-forge supports two engines.

## DuckDB (default)

In-process analytical database. Zero configuration, no external services.

```python
store = FeatureStore("my_features/")           # uses DuckDB by default
store = FeatureStore("my_features/", engine="duckdb")  # explicit
```

**PIT join implementation:**
- Passthrough features: native `ASOF LEFT JOIN` (available since DuckDB 0.8)
- Aggregation features: `LEFT JOIN` with time-bounded `WHERE` clause + `GROUP BY`

**Best for:** local development, CI/CD pipelines, datasets up to ~100GB. Runs entirely on your machine with no setup.

## PySpark (optional)

Distributed SQL engine for large-scale data.

```bash
pip install fforge[spark]
```

```python
store = FeatureStore("my_features/", engine="spark")
```

**PIT join implementation:**
- Passthrough features: `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ts DESC NULLS LAST)` + filter `rn = 1`
- Aggregation features: same time-bounded `LEFT JOIN` + `GROUP BY`, with Spark SQL `INTERVAL` syntax

**Best for:** Databricks notebooks, Spark clusters, datasets larger than single-machine memory.

**Inside Databricks:** the Spark engine automatically detects and reuses the active SparkSession. No additional configuration needed.

**Outside Databricks:** creates a local SparkSession with `master("local[*]")`. Requires Java runtime.

## Choosing an engine

| Criteria | DuckDB | PySpark |
|----------|--------|---------|
| Setup | `pip install fforge` | `pip install fforge[spark]` + Java |
| Data size | Up to ~100GB | Unlimited (cluster) |
| Speed (small data) | Very fast | Slow (JVM startup overhead) |
| Speed (large data) | Good | Better (distributed) |
| Databricks | Works (via SQL Warehouse connector) | Native |
| CI/CD | Ideal | Heavy |

**Rule of thumb:** use DuckDB unless you're working with data that doesn't fit on a single machine or you're inside a Databricks notebook.

## Engine in YAML

You can set the default engine in any YAML file in your feature repo:

```yaml
engine: spark   # default engine for this repo
```

The constructor parameter overrides the YAML setting:

```python
# YAML says spark, but this uses duckdb
store = FeatureStore("my_features/", engine="duckdb")
```

## Engine in CLI

The `materialize` command accepts an `--engine` flag:

```bash
feature-forge materialize customer_features \
    --start 2025-01-01 --end 2025-06-01 \
    --entity-key customer_id --entity-values 1,2,3 \
    --engine spark
```
