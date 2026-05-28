"""PySpark query engine implementation.

Requires: pip install fforge[spark]
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from feature_forge.exceptions import EngineError


class SparkEngine:
    """Query engine backed by PySpark (for Databricks / Spark clusters)."""

    def __init__(self) -> None:
        self._spark: Any = None  # SparkSession, typed as Any to avoid import

    @property
    def spark(self) -> Any:
        if self._spark is None:
            self.connect()
        return self._spark

    def connect(self) -> None:
        if self._spark is not None:
            return
        try:
            from pyspark.sql import SparkSession

            # Try to get existing session (e.g. inside Databricks)
            self._spark = SparkSession.getActiveSession()
            if self._spark is None:
                self._spark = (
                    SparkSession.builder
                    .master("local[*]")
                    .appName("feature-forge")
                    .config("spark.sql.session.timeZone", "UTC")
                    .config("spark.sql.parquet.outputTimestampType", "TIMESTAMP_MICROS")
                    .config("spark.sql.parquet.int96RebaseModeInRead", "CORRECTED")
                    .config("spark.sql.parquet.datetimeRebaseModeInRead", "CORRECTED")
                    .getOrCreate()
                )
        except ImportError as e:
            raise EngineError(
                "SparkEngine requires PySpark. "
                "Install with: pip install fforge[spark]"
            ) from e

    def close(self) -> None:
        if self._spark is not None:
            self._spark.stop()
            self._spark = None

    def register_view(self, view_name: str, data: Any) -> None:
        """Register data as a Spark temp view.

        Supports:
        - pandas DataFrame: converted to Spark DF and registered
        - str (parquet path): read via spark.read.parquet and registered
        """
        if isinstance(data, pd.DataFrame):
            # Floor nanosecond timestamps to microsecond for Spark compatibility
            pdf = data.copy()
            for col in pdf.select_dtypes(include=["datetime64[ns]"]).columns:
                pdf[col] = pdf[col].dt.floor("us")
            spark_df = self.spark.createDataFrame(pdf)
            spark_df.createOrReplaceTempView(view_name)
        elif isinstance(data, str):
            # Read via pandas to handle nanosecond timestamps that Spark can't read
            import pyarrow.parquet as pq
            table = pq.read_table(data)
            # Convert nanosecond timestamps to microsecond for Spark compatibility
            pdf = table.to_pandas(timestamp_as_object=False)
            for col in pdf.select_dtypes(include=["datetime64[ns]"]).columns:
                pdf[col] = pdf[col].dt.floor("us")
            spark_df = self.spark.createDataFrame(pdf)
            spark_df.createOrReplaceTempView(view_name)
        else:
            raise EngineError(
                f"Cannot register data of type {type(data).__name__}. "
                f"Expected pandas DataFrame or file path string."
            )

    def execute_sql(self, sql: str) -> pd.DataFrame:
        try:
            return self.spark.sql(sql).toPandas()
        except Exception as e:
            raise EngineError(f"Spark SQL execution failed: {e}\nQuery:\n{sql}") from e

    def write_parquet(self, sql: str, path: str) -> None:
        try:
            self.spark.sql(sql).write.mode("overwrite").parquet(path)
        except Exception as e:
            raise EngineError(f"Failed to write Parquet to {path}: {e}") from e

    def __enter__(self) -> SparkEngine:
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
