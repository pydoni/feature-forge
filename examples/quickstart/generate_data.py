"""Generate sample Parquet data for the quickstart example."""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "feature_repo" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Transactions: 3 customers, ~20 transactions over 2 months
transactions = pd.DataFrame(
    {
        "customer_id": [1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 1, 2, 3, 1, 2],
        "amount": [
            50, 120, 30, 200, 80, 300, 150, 45, 90, 25, 60, 180, 95, 40, 110,
            75, 220, 55, 160, 35,
        ],
        "event_timestamp": pd.to_datetime(
            [
                "2025-01-02", "2025-01-05", "2025-01-08", "2025-01-12", "2025-01-15",
                "2025-01-03", "2025-01-07", "2025-01-14", "2025-01-20", "2025-01-01",
                "2025-01-04", "2025-01-09", "2025-01-11", "2025-01-18", "2025-01-25",
                "2025-01-22", "2025-01-28", "2025-02-01", "2025-02-05", "2025-02-10",
            ]
        ),
        "merchant_id": [
            "m1", "m2", "m1", "m3", "m2", "m3", "m1", "m2", "m3", "m1",
            "m2", "m3", "m1", "m2", "m1", "m3", "m2", "m1", "m2", "m3",
        ],
    }
)
transactions.to_parquet(DATA_DIR / "transactions.parquet", index=False)
print(f"Wrote {len(transactions)} transactions to {DATA_DIR / 'transactions.parquet'}")

# Profiles: customer demographic data
profiles = pd.DataFrame(
    {
        "customer_id": [1, 2, 3],
        "age": [34, 28, 45],
        "updated_at": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-01"]),
    }
)
profiles.to_parquet(DATA_DIR / "profiles.parquet", index=False)
print(f"Wrote {len(profiles)} profiles to {DATA_DIR / 'profiles.parquet'}")
