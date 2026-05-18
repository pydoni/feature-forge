"""Databricks example: using feature-forge with Unity Catalog tables.

Prerequisites:
    pip install feature-forge[databricks]
    export DATABRICKS_HOST=adb-123456.azuredatabricks.net
    export DATABRICKS_TOKEN=dapi...
    export DATABRICKS_WAREHOUSE_ID=abc123def

If running inside a Databricks notebook, the Spark engine is auto-detected
and no token/host configuration is needed.
"""

from pathlib import Path

import pandas as pd

from feature_forge import FeatureStore

REPO_PATH = Path(__file__).parent / "feature_repo"


def main() -> None:
    # Outside Databricks: uses DuckDB + databricks-sql-connector
    store = FeatureStore(REPO_PATH)

    # Inside Databricks: use Spark engine for native performance
    # store = FeatureStore(REPO_PATH, engine="spark")

    labels = pd.DataFrame(
        {
            "doctor_id": [1001, 1002, 1003],
            "event_timestamp": pd.to_datetime(
                ["2025-06-01", "2025-06-01", "2025-06-01"]
            ),
        }
    )

    df = store.get_features_table(
        entity_df=labels,
        feature_views=["doctor_prescription_features", "doctor_event_features"],
    )

    print(df.to_string(index=False))
    store.close()


if __name__ == "__main__":
    main()
