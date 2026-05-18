"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_repo_path() -> Path:
    return FIXTURES_DIR / "valid_repo"


@pytest.fixture
def invalid_repo_path() -> Path:
    return FIXTURES_DIR / "invalid_repo"


@pytest.fixture
def sample_transactions(tmp_path: Path) -> Path:
    df = pd.DataFrame(
        {
            "customer_id": [1, 1, 1, 2, 2],
            "amount": [100.0, 200.0, 50.0, 300.0, 150.0],
            "event_timestamp": pd.to_datetime(
                [
                    "2025-01-01",
                    "2025-01-05",
                    "2025-01-10",
                    "2025-01-03",
                    "2025-01-08",
                ]
            ),
            "merchant_id": ["m1", "m2", "m1", "m3", "m2"],
        }
    )
    path = tmp_path / "transactions.parquet"
    df.to_parquet(path, index=False)
    return path


@pytest.fixture
def sample_user_profiles(tmp_path: Path) -> Path:
    df = pd.DataFrame(
        {
            "customer_id": [1, 2],
            "age": [34, 28],
            "updated_at": pd.to_datetime(["2025-01-01", "2025-01-01"]),
        }
    )
    path = tmp_path / "user_profiles.parquet"
    df.to_parquet(path, index=False)
    return path


@pytest.fixture
def feature_repo(tmp_path: Path, sample_transactions: Path, sample_user_profiles: Path) -> Path:
    """Create a complete feature repo with YAML and sample data."""
    import shutil

    # Copy YAML files
    for yml in (FIXTURES_DIR / "valid_repo").glob("*.yml"):
        shutil.copy(yml, tmp_path / yml.name)

    # Create data directory and move parquet files
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    shutil.copy(sample_transactions, data_dir / "transactions.parquet")
    shutil.copy(sample_user_profiles, data_dir / "user_profiles.parquet")

    return tmp_path
