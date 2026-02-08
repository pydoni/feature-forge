"""Tests for the PIT join SQL builder and execution.

Critical test cases:
1. No data leakage (future data never appears)
2. Correct window boundaries
3. Null handling (no data in window -> null)
4. Multiple entities get independent calculations
5. Duplicate entity rows produce identical results
6. Passthrough features (ASOF JOIN)
7. Mixed passthrough + aggregation
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from feature_forge.engine.retrieval import retrieve_features
from feature_forge.engines.duckdb_engine import DuckDBEngine
from feature_forge.registry.loader import load_registry
from feature_forge.registry.models import FeatureRegistry


@pytest.fixture
def transactions_parquet(tmp_path: Path) -> Path:
    """Transactions with known timestamps for testing PIT correctness."""
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
    """Feature repo with known data for PIT join testing."""
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


@pytest.fixture
def engine() -> DuckDBEngine:
    eng = DuckDBEngine()
    eng.connect()
    return eng


class TestNoDataLeakage:
    """The most critical test: future data must never appear in results."""

    def test_aggregation_no_future_data(
        self, pit_registry: FeatureRegistry, engine: DuckDBEngine, pit_repo: Path
    ):
        # Query features as of Jan 8: should only see transactions on or before Jan 8
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
            engine=engine,
            repo_path=str(pit_repo),
        )

        # Customer 1 transactions: Jan 5 (within 7d window: Jan 1 < ts <= Jan 8)
        # Jan 1 is exactly at boundary (8 - 7 = 1), excluded by strict >
        # Jan 10, Jan 20 are FUTURE -> must NOT be counted
        assert result["count_7d"].iloc[0] == 1

    def test_passthrough_no_future_data(
        self, pit_registry: FeatureRegistry, engine: DuckDBEngine, pit_repo: Path
    ):
        # Query profile as of Jan 10: should see age=34 (Jan 1 update), not 35 (Jan 12 update)
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
            engine=engine,
            repo_path=str(pit_repo),
        )

        assert result["customer_age"].iloc[0] == 34

    def test_passthrough_sees_update_after_date(
        self, pit_registry: FeatureRegistry, engine: DuckDBEngine, pit_repo: Path
    ):
        # Query profile as of Jan 15: should see age=35 (Jan 12 update)
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
            engine=engine,
            repo_path=str(pit_repo),
        )

        assert result["customer_age"].iloc[0] == 35


class TestWindowBoundaries:
    def test_7d_window_excludes_old_data(
        self, pit_registry: FeatureRegistry, engine: DuckDBEngine, pit_repo: Path
    ):
        # As of Jan 10, 7d window = Jan 4 to Jan 10
        # Customer 1: Jan 5 (in), Jan 10 (in), Jan 1 (OUT - too old)
        entity_df = pd.DataFrame(
            {
                "customer_id": [1],
                "event_timestamp": pd.to_datetime(["2025-01-10"]),
            }
        )

        result = retrieve_features(
            entity_df=entity_df,
            feature_view_names=["txn_count_7d"],
            registry=pit_registry,
            engine=engine,
            repo_path=str(pit_repo),
        )

        assert result["count_7d"].iloc[0] == 2  # Jan 5 + Jan 10

    def test_30d_window_includes_more(
        self, pit_registry: FeatureRegistry, engine: DuckDBEngine, pit_repo: Path
    ):
        # As of Jan 25, 30d window covers all of January
        # Customer 1 has 4 transactions: Jan 1, 5, 10, 20
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
            engine=engine,
            repo_path=str(pit_repo),
        )

        assert result["count_30d"].iloc[0] == 4
        assert result["max_amount_30d"].iloc[0] == 300.0
        expected_avg = (100.0 + 200.0 + 50.0 + 300.0) / 4
        assert abs(result["avg_amount_30d"].iloc[0] - expected_avg) < 0.01


class TestNullHandling:
    def test_no_data_in_window_returns_null(
        self, pit_registry: FeatureRegistry, engine: DuckDBEngine, pit_repo: Path
    ):
        # Query for customer 1 on Dec 20 (before any transaction)
        entity_df = pd.DataFrame(
            {
                "customer_id": [1],
                "event_timestamp": pd.to_datetime(["2024-12-20"]),
            }
        )

        result = retrieve_features(
            entity_df=entity_df,
            feature_view_names=["txn_count_7d"],
            registry=pit_registry,
            engine=engine,
            repo_path=str(pit_repo),
        )

        assert result["count_7d"].iloc[0] == 0  # COUNT returns 0 for no matches

    def test_passthrough_null_when_no_prior_data(
        self, pit_registry: FeatureRegistry, engine: DuckDBEngine, pit_repo: Path
    ):
        # Customer 2 profile updated on Jan 1. Query on Dec 15 -> no data -> null
        entity_df = pd.DataFrame(
            {
                "customer_id": [2],
                "event_timestamp": pd.to_datetime(["2024-12-15"]),
            }
        )

        result = retrieve_features(
            entity_df=entity_df,
            feature_view_names=["customer_profile"],
            registry=pit_registry,
            engine=engine,
            repo_path=str(pit_repo),
        )

        assert pd.isna(result["customer_age"].iloc[0])


class TestMultiEntity:
    def test_independent_calculations_per_entity(
        self, pit_registry: FeatureRegistry, engine: DuckDBEngine, pit_repo: Path
    ):
        # Same timestamp, different customers -> different features
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
            engine=engine,
            repo_path=str(pit_repo),
        )

        # Customer 1: Jan 5, Jan 10 -> count=2
        # Customer 2: Jan 3 (OUT of 7d), Jan 8 -> count=1
        c1 = result[result["customer_id"] == 1]["count_7d"].iloc[0]
        c2 = result[result["customer_id"] == 2]["count_7d"].iloc[0]
        assert c1 == 2
        assert c2 == 1


class TestDuplicateEntityRows:
    def test_duplicate_rows_produce_identical_features(
        self, pit_registry: FeatureRegistry, engine: DuckDBEngine, pit_repo: Path
    ):
        entity_df = pd.DataFrame(
            {
                "customer_id": [1, 1],
                "event_timestamp": pd.to_datetime(["2025-01-10", "2025-01-10"]),
            }
        )

        result = retrieve_features(
            entity_df=entity_df,
            feature_view_names=["txn_count_7d"],
            registry=pit_registry,
            engine=engine,
            repo_path=str(pit_repo),
        )

        assert len(result) == 2
        assert result["count_7d"].iloc[0] == result["count_7d"].iloc[1]


class TestMultipleFeatureViews:
    def test_join_agg_and_passthrough(
        self, pit_registry: FeatureRegistry, engine: DuckDBEngine, pit_repo: Path
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
            engine=engine,
            repo_path=str(pit_repo),
        )

        # Should have aggregation features + passthrough features
        assert "count_30d" in result.columns
        assert "avg_amount_30d" in result.columns
        assert "customer_age" in result.columns
        # Customer 1 as of Jan 15: txns Jan 1, 5, 10 (3 in 30d window)
        assert result["count_30d"].iloc[0] == 3
        # Age updated on Jan 12 -> 35
        assert result["customer_age"].iloc[0] == 35

    def test_multiple_timestamps_per_entity(
        self, pit_registry: FeatureRegistry, engine: DuckDBEngine, pit_repo: Path
    ):
        """Same entity at different points in time gets different features."""
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
            engine=engine,
            repo_path=str(pit_repo),
        )

        # Jan 5: only Jan 1 and Jan 5 -> count=2
        # Jan 25: all 4 txns -> count=4
        row_jan5 = result[result["event_timestamp"] == pd.Timestamp("2025-01-05")]
        row_jan25 = result[result["event_timestamp"] == pd.Timestamp("2025-01-25")]
        assert row_jan5["count_30d"].iloc[0] == 2
        assert row_jan25["count_30d"].iloc[0] == 4
