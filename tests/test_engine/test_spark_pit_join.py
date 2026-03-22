"""Tests for SparkEngine PIT joins.

Mirrors the DuckDB PIT join tests to ensure identical results.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from feature_forge.engine.retrieval import retrieve_features
from feature_forge.engines.spark_engine import SparkEngine
from feature_forge.registry.loader import load_registry
from feature_forge.registry.models import FeatureRegistry

pytestmark = pytest.mark.spark


@pytest.fixture(scope="module")
def spark_engine():
    """Create a single SparkEngine for all tests in this module."""
    engine = SparkEngine()
    engine.connect()
    yield engine
    engine.close()


@pytest.fixture
def transactions_parquet(tmp_path: Path) -> Path:
    df = pd.DataFrame(
        {
            "customer_id": [1, 1, 1, 1, 2, 2, 2],
            "amount": [100.0, 200.0, 50.0, 300.0, 150.0, 250.0, 75.0],
            "event_timestamp": pd.to_datetime(
                [
                    "2025-01-01",
                    "2025-01-05",
                    "2025-01-10",
                    "2025-01-20",
                    "2025-01-03",
                    "2025-01-08",
                    "2025-01-15",
                ]
            ),
            "merchant_id": ["m1", "m2", "m1", "m3", "m3", "m2", "m1"],
        }
    )
    path = tmp_path / "data" / "transactions.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


@pytest.fixture
def profiles_parquet(tmp_path: Path) -> Path:
    df = pd.DataFrame(
        {
            "customer_id": [1, 1, 2],
            "age": [34, 35, 28],
            "updated_at": pd.to_datetime(["2025-01-01", "2025-01-12", "2025-01-01"]),
        }
    )
    path = tmp_path / "data" / "user_profiles.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


@pytest.fixture
def pit_repo(tmp_path: Path, transactions_parquet: Path, profiles_parquet: Path) -> Path:
    (tmp_path / "entities.yml").write_text(
        "entities:\n"
        "  - name: customer\n"
        "    join_keys: [customer_id]\n"
    )
    (tmp_path / "sources.yml").write_text(
        "sources:\n"
        "  - name: transactions\n"
        "    backend: parquet\n"
        "    path: data/transactions.parquet\n"
        "    entity: customer\n"
        "    timestamp_column: event_timestamp\n"
        "    columns:\n"
        "      - { name: customer_id, dtype: int64 }\n"
        "      - { name: amount, dtype: float64 }\n"
        "      - { name: event_timestamp, dtype: timestamp }\n"
        "      - { name: merchant_id, dtype: varchar }\n"
        "  - name: user_profiles\n"
        "    backend: parquet\n"
        "    path: data/user_profiles.parquet\n"
        "    entity: customer\n"
        "    timestamp_column: updated_at\n"
        "    columns:\n"
        "      - { name: customer_id, dtype: int64 }\n"
        "      - { name: age, dtype: int32 }\n"
        "      - { name: updated_at, dtype: timestamp }\n"
    )
    (tmp_path / "features.yml").write_text(
        "feature_views:\n"
        "  - name: txn_count_7d\n"
        "    entity: customer\n"
        "    source: transactions\n"
        "    features:\n"
        "      - name: count_7d\n"
        "        dtype: int64\n"
        "        aggregation: { function: count, column: amount, window: 7d }\n"
        "  - name: txn_agg_30d\n"
        "    entity: customer\n"
        "    source: transactions\n"
        "    features:\n"
        "      - name: count_30d\n"
        "        dtype: int64\n"
        "        aggregation: { function: count, column: amount, window: 30d }\n"
        "      - name: avg_amount_30d\n"
        "        dtype: float64\n"
        "        aggregation: { function: avg, column: amount, window: 30d }\n"
        "      - name: max_amount_30d\n"
        "        dtype: float64\n"
        "        aggregation: { function: max, column: amount, window: 30d }\n"
        "  - name: customer_profile\n"
        "    entity: customer\n"
        "    source: user_profiles\n"
        "    features:\n"
        "      - name: customer_age\n"
        "        dtype: int32\n"
        "        column: age\n"
    )
    return tmp_path


@pytest.fixture
def pit_registry(pit_repo: Path) -> FeatureRegistry:
    return load_registry(pit_repo)


class TestSparkNoDataLeakage:
    def test_aggregation_no_future_data(
        self, pit_registry: FeatureRegistry, spark_engine: SparkEngine, pit_repo: Path
    ):
        entity_df = pd.DataFrame(
            {
                "customer_id": [1],
                "event_timestamp": pd.to_datetime(["2025-01-08"]),
            }
        )
        result = retrieve_features(
            entity_df=entity_df,
            feature_view_names=["txn_count_7d"],
            registry=pit_registry,
            engine=spark_engine,
            repo_path=str(pit_repo),
        )
        # Window: Jan 1 < ts <= Jan 8 -> only Jan 5
        assert result["count_7d"].iloc[0] == 1

    def test_passthrough_no_future_data(
        self, pit_registry: FeatureRegistry, spark_engine: SparkEngine, pit_repo: Path
    ):
        entity_df = pd.DataFrame(
            {
                "customer_id": [1],
                "event_timestamp": pd.to_datetime(["2025-01-10"]),
            }
        )
        result = retrieve_features(
            entity_df=entity_df,
            feature_view_names=["customer_profile"],
            registry=pit_registry,
            engine=spark_engine,
            repo_path=str(pit_repo),
        )
        assert result["customer_age"].iloc[0] == 34

    def test_passthrough_sees_update_after_date(
        self, pit_registry: FeatureRegistry, spark_engine: SparkEngine, pit_repo: Path
    ):
        entity_df = pd.DataFrame(
            {
                "customer_id": [1],
                "event_timestamp": pd.to_datetime(["2025-01-15"]),
            }
        )
        result = retrieve_features(
            entity_df=entity_df,
            feature_view_names=["customer_profile"],
            registry=pit_registry,
            engine=spark_engine,
            repo_path=str(pit_repo),
        )
        assert result["customer_age"].iloc[0] == 35


class TestSparkWindowBoundaries:
    def test_30d_window(
        self, pit_registry: FeatureRegistry, spark_engine: SparkEngine, pit_repo: Path
    ):
        entity_df = pd.DataFrame(
            {
                "customer_id": [1],
                "event_timestamp": pd.to_datetime(["2025-01-25"]),
            }
        )
        result = retrieve_features(
            entity_df=entity_df,
            feature_view_names=["txn_agg_30d"],
            registry=pit_registry,
            engine=spark_engine,
            repo_path=str(pit_repo),
        )
        assert result["count_30d"].iloc[0] == 4
        assert result["max_amount_30d"].iloc[0] == 300.0


class TestSparkMultiEntity:
    def test_independent_calculations(
        self, pit_registry: FeatureRegistry, spark_engine: SparkEngine, pit_repo: Path
    ):
        entity_df = pd.DataFrame(
            {
                "customer_id": [1, 2],
                "event_timestamp": pd.to_datetime(["2025-01-10", "2025-01-10"]),
            }
        )
        result = retrieve_features(
            entity_df=entity_df,
            feature_view_names=["txn_count_7d"],
            registry=pit_registry,
            engine=spark_engine,
            repo_path=str(pit_repo),
        )
        c1 = result[result["customer_id"] == 1]["count_7d"].iloc[0]
        c2 = result[result["customer_id"] == 2]["count_7d"].iloc[0]
        assert c1 == 2  # Jan 5, Jan 10
        assert c2 == 1  # Jan 8


class TestSparkMultipleViews:
    def test_agg_and_passthrough_combined(
        self, pit_registry: FeatureRegistry, spark_engine: SparkEngine, pit_repo: Path
    ):
        entity_df = pd.DataFrame(
            {
                "customer_id": [1],
                "event_timestamp": pd.to_datetime(["2025-01-15"]),
            }
        )
        result = retrieve_features(
            entity_df=entity_df,
            feature_view_names=["txn_agg_30d", "customer_profile"],
            registry=pit_registry,
            engine=spark_engine,
            repo_path=str(pit_repo),
        )
        assert "count_30d" in result.columns
        assert "customer_age" in result.columns
        assert result["count_30d"].iloc[0] == 3
        assert result["customer_age"].iloc[0] == 35

    def test_multiple_timestamps_per_entity(
        self, pit_registry: FeatureRegistry, spark_engine: SparkEngine, pit_repo: Path
    ):
        entity_df = pd.DataFrame(
            {
                "customer_id": [1, 1],
                "event_timestamp": pd.to_datetime(["2025-01-05", "2025-01-25"]),
            }
        )
        result = retrieve_features(
            entity_df=entity_df,
            feature_view_names=["txn_agg_30d"],
            registry=pit_registry,
            engine=spark_engine,
            repo_path=str(pit_repo),
        )
        row_jan5 = result[result["event_timestamp"] == pd.Timestamp("2025-01-05")]
        row_jan25 = result[result["event_timestamp"] == pd.Timestamp("2025-01-25")]
        assert row_jan5["count_30d"].iloc[0] == 2
        assert row_jan25["count_30d"].iloc[0] == 4
