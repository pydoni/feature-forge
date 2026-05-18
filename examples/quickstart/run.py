"""Quickstart example: training, inference, and backfill with feature-forge."""

from pathlib import Path

import pandas as pd

from feature_forge import FeatureStore

REPO_PATH = Path(__file__).parent / "feature_repo"


def main() -> None:
    store = FeatureStore(REPO_PATH)

    # 1. Validate the registry
    result = store.validate()
    print(f"Registry valid: {result.is_valid}")
    if not result.is_valid:
        for issue in result.issues:
            print(f"  [{issue.level}] {issue.source_name}: {issue.message}")
        return

    # 2. Training mode: get features for labeled data
    print("\n--- Training Mode ---")
    labels = pd.DataFrame(
        {
            "customer_id": [1, 2, 3, 1],
            "event_timestamp": pd.to_datetime(
                ["2025-01-15", "2025-01-20", "2025-01-25", "2025-02-05"]
            ),
            "is_fraud": [0, 0, 1, 0],
        }
    )

    training_df = store.get_features_table(
        entity_df=labels,
        feature_views=["customer_txn_features", "customer_profile_features"],
    )
    print(training_df.to_string(index=False))

    # 3. Inference mode: get features for current entities
    print("\n--- Inference Mode ---")
    inference_df = store.get_features_table(
        entity_ids={"customer_id": [1, 2, 3]},
        feature_views=["customer_txn_features"],
    )
    print(inference_df[["customer_id", "txn_count_7d", "avg_amount_30d"]].to_string(index=False))

    # 4. Historical backfill: features for every day in a range
    print("\n--- Historical Backfill ---")
    backfill_df = store.get_features_table(
        entity_ids={"customer_id": [1]},
        feature_views=["customer_txn_features"],
        start_date="2025-01-10",
        end_date="2025-01-15",
        interval="1d",
    )
    print(backfill_df[["customer_id", "event_timestamp", "txn_count_7d"]].to_string(index=False))

    # 5. Materialize to Parquet
    print("\n--- Materialization ---")
    output = store.materialize(
        feature_views=["customer_txn_features"],
        entity_ids={"customer_id": [1, 2, 3]},
        start_date="2025-01-10",
        end_date="2025-01-20",
        interval="1d",
    )
    print(f"Materialized to: {output}")

    store.close()


if __name__ == "__main__":
    main()
