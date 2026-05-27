# CLI Reference

feature-forge includes a CLI for common operations. All commands support `--repo` to specify the feature repo directory (defaults to current directory).

## `feature-forge init`

Create a new feature repo with template YAML files.

```bash
feature-forge init [PATH]
```

Creates `entities.yml`, `sources.yml`, and `features.yml` with example content. Skips files that already exist.

**Example:**
```bash
feature-forge init my_features/
```

## `feature-forge validate`

Check the feature registry for errors.

```bash
feature-forge validate [--repo PATH]
```

Validates:
- YAML syntax and schema
- Cross-references (entity/source links)
- Source accessibility (file exists, credentials available)
- Column declarations match actual data

Exit code `0` if valid, `1` if errors found.

**Example:**
```bash
feature-forge validate --repo my_features/
```

## `feature-forge list`

List registered entities, sources, or feature views.

```bash
feature-forge list {entities|sources|features} [--repo PATH]
```

**Examples:**
```bash
feature-forge list entities --repo my_features/
feature-forge list sources --repo my_features/
feature-forge list features --repo my_features/
```

## `feature-forge describe`

Show detailed info about a feature view, including all its features with types and modes.

```bash
feature-forge describe FEATURE_VIEW [--repo PATH]
```

**Example:**
```bash
feature-forge describe customer_txn_features --repo my_features/
```

## `feature-forge materialize`

Compute features and save to a Parquet file.

```bash
feature-forge materialize FEATURE_VIEW \
    --start DATE \
    --end DATE \
    --entity-key KEY_NAME \
    --entity-values VALUE1,VALUE2,... \
    [--interval INTERVAL] \
    [--output PATH] \
    [--engine ENGINE] \
    [--repo PATH]
```

**Required flags:**
- `--start`: start date (YYYY-MM-DD)
- `--end`: end date (YYYY-MM-DD)
- `--entity-key`: name of the entity join key column
- `--entity-values`: comma-separated list of entity values

**Optional flags:**
- `--interval`: time step between data points (default: `1d`)
- `--output`: output Parquet path (default: `.forge/materialized/<view>.parquet`)
- `--engine`: query engine, `duckdb` or `spark` (default: `duckdb`)

**Example:**
```bash
feature-forge materialize customer_txn_features \
    --start 2025-01-01 \
    --end 2025-06-01 \
    --entity-key customer_id \
    --entity-values 101,102,103 \
    --interval 7d \
    --engine duckdb \
    --repo my_features/
```

## `feature-forge --version`

Show the installed version.

```bash
feature-forge --version
```
