"""Integration tests for FeatureStore (end-to-end)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from feature_forge import FeatureStore
from feature_forge.exceptions import FeatureForgeError


class TestFeatureStoreInit:
    def test_init_from_valid_repo(self, feature_repo: Path):
        store = FeatureStore(feature_repo)
        assert len(store.entities) == 2
        assert len(store.sources) == 2
        assert len(store.feature_views) == 2
        store.close()

    def test_init_context_manager(self, feature_repo: Path):
        with FeatureStore(feature_repo) as store:
            assert len(store.entities) == 2

    def test_validate(self, feature_repo: Path):
        with FeatureStore(feature_repo) as store:
            result = store.validate()
            assert result.is_valid


class TestGetFeaturesTableWithEntityDf:
    def test_training_mode(self, feature_repo: Path):
        """Pass entity_df with historical timestamps (training use case)."""
        entity_df = pd.DataFrame(
            {
                "customer_id": [1, 2],
                "event_timestamp": pd.to_datetime(["2025-01-10", "2025-01-10"]),
            }
        )
        with FeatureStore(feature_repo) as store:
            result = store.get_features_table(
                entity_df=entity_df,
                feature_views=["customer_transaction_features"],
            )

        assert len(result) == 2
        assert "transaction_count_7d" in result.columns
        assert "avg_transaction_amount_30d" in result.columns
        assert "max_transaction_amount_30d" in result.columns
        # Original columns preserved
        assert "customer_id" in result.columns
        assert "event_timestamp" in result.columns

    def test_passthrough_features(self, feature_repo: Path):
        entity_df = pd.DataFrame(
            {
                "customer_id": [1],
                "event_timestamp": pd.to_datetime(["2025-01-10"]),
            }
        )
        with FeatureStore(feature_repo) as store:
            result = store.get_features_table(
                entity_df=entity_df,
                feature_views=["customer_profile_features"],
            )

        assert "customer_age" in result.columns

    def test_multiple_feature_views(self, feature_repo: Path):
        entity_df = pd.DataFrame(
            {
                "customer_id": [1],
                "event_timestamp": pd.to_datetime(["2025-01-10"]),
            }
        )
        with FeatureStore(feature_repo) as store:
            result = store.get_features_table(
                entity_df=entity_df,
                feature_views=[
                    "customer_transaction_features",
                    "customer_profile_features",
                ],
            )

        assert "transaction_count_7d" in result.columns
        assert "customer_age" in result.columns

    def test_extra_columns_preserved(self, feature_repo: Path):
        """Extra columns in entity_df (like labels) should be preserved."""
        entity_df = pd.DataFrame(
            {
                "customer_id": [1, 2],
                "event_timestamp": pd.to_datetime(["2025-01-10", "2025-01-10"]),
                "is_fraud": [1, 0],
            }
        )
        with FeatureStore(feature_repo) as store:
            result = store.get_features_table(
                entity_df=entity_df,
                feature_views=["customer_transaction_features"],
            )

        assert "is_fraud" in result.columns
        assert list(result["is_fraud"]) == [1, 0]


class TestGetFeaturesTableWithEntityIds:
    def test_inference_mode(self, feature_repo: Path):
        """Pass entity_ids without dates (inference at now)."""
        with FeatureStore(feature_repo) as store:
            result = store.get_features_table(
                entity_ids={"customer_id": [1, 2]},
                feature_views=["customer_transaction_features"],
            )

        assert len(result) == 2
        assert "customer_id" in result.columns
        assert "event_timestamp" in result.columns
        assert "transaction_count_7d" in result.columns

    def test_historical_backfill(self, feature_repo: Path):
        """Pass entity_ids + date range (backfill mode)."""
        with FeatureStore(feature_repo) as store:
            result = store.get_features_table(
                entity_ids={"customer_id": [1]},
                feature_views=["customer_transaction_features"],
                start_date="2025-01-05",
                end_date="2025-01-10",
                interval="1d",
            )

        # 6 days: Jan 5, 6, 7, 8, 9, 10
        assert len(result) == 6
        assert "transaction_count_7d" in result.columns

    def test_backfill_multiple_entities(self, feature_repo: Path):
        """Cartesian product: 2 entities x 3 days = 6 rows."""
        with FeatureStore(feature_repo) as store:
            result = store.get_features_table(
                entity_ids={"customer_id": [1, 2]},
                feature_views=["customer_transaction_features"],
                start_date="2025-01-08",
                end_date="2025-01-10",
                interval="1d",
            )

        assert len(result) == 6  # 2 customers x 3 days


class TestGetFeaturesTableErrors:
    def test_both_entity_df_and_ids_raises(self, feature_repo: Path):
        entity_df = pd.DataFrame(
            {
                "customer_id": [1],
                "event_timestamp": pd.to_datetime(["2025-01-10"]),
            }
        )
        with FeatureStore(feature_repo) as store:
            with pytest.raises(FeatureForgeError, match="not both"):
                store.get_features_table(
                    entity_df=entity_df,
                    entity_ids={"customer_id": [1]},
                    feature_views=["customer_transaction_features"],
                )

    def test_neither_entity_df_nor_ids_raises(self, feature_repo: Path):
        with FeatureStore(feature_repo) as store:
            with pytest.raises(FeatureForgeError, match="Must provide"):
                store.get_features_table(
                    feature_views=["customer_transaction_features"],
                )

    def test_backfill_without_interval_raises(self, feature_repo: Path):
        with FeatureStore(feature_repo) as store:
            with pytest.raises(FeatureForgeError, match="interval"):
                store.get_features_table(
                    entity_ids={"customer_id": [1]},
                    feature_views=["customer_transaction_features"],
                    start_date="2025-01-01",
                    end_date="2025-01-10",
                )


class TestMaterialize:
    def test_materialize_default_path(self, feature_repo: Path):
        with FeatureStore(feature_repo) as store:
            output = store.materialize(
                feature_views=["customer_transaction_features"],
                entity_ids={"customer_id": [1, 2]},
                start_date="2025-01-05",
                end_date="2025-01-10",
                interval="1d",
            )

        assert output.exists()
        assert output.suffix == ".parquet"
        assert ".forge" in str(output)

        # Read back and verify
        df = pd.read_parquet(output)
        assert len(df) == 12  # 2 customers x 6 days
        assert "transaction_count_7d" in df.columns

    def test_materialize_custom_path(self, feature_repo: Path, tmp_path: Path):
        custom_output = tmp_path / "output" / "features.parquet"
        with FeatureStore(feature_repo) as store:
            output = store.materialize(
                feature_views=["customer_transaction_features"],
                entity_ids={"customer_id": [1]},
                start_date="2025-01-05",
                end_date="2025-01-07",
                interval="1d",
                output_path=custom_output,
            )

        assert output == custom_output
        assert output.exists()
        df = pd.read_parquet(output)
        assert len(df) == 3


class TestIntervalParsing:
    def test_valid_intervals(self):
        assert FeatureStore._parse_interval_to_freq("1d") == "1D"
        assert FeatureStore._parse_interval_to_freq("7d") == "7D"
        assert FeatureStore._parse_interval_to_freq("1h") == "1h"
        assert FeatureStore._parse_interval_to_freq("30m") == "30min"

    def test_invalid_interval(self):
        with pytest.raises(FeatureForgeError):
            FeatureStore._parse_interval_to_freq("abc")
