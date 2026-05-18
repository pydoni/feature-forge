"""Tests for the Databricks backend (mocked, no real connection)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from feature_forge.backends.databricks import DatabricksBackend, _is_inside_databricks
from feature_forge.exceptions import BackendError
from feature_forge.registry.models import Column, Source


@pytest.fixture
def databricks_backend() -> DatabricksBackend:
    return DatabricksBackend()


@pytest.fixture
def databricks_source() -> Source:
    return Source(
        name="prescriptions",
        backend="databricks",
        table="catalog.schema.prescriptions",
        host="adb-123.azuredatabricks.net",
        warehouse_id="abc123",
        entity="doctor",
        timestamp_column="dt_prescricao",
        columns=[
            Column(name="doctor_id", dtype="int64"),
            Column(name="dt_prescricao", dtype="timestamp"),
        ],
    )


class TestDatabricksDetection:
    def test_not_inside_databricks(self):
        with patch.dict(os.environ, {}, clear=True):
            assert not _is_inside_databricks()

    def test_inside_databricks(self):
        with patch.dict(os.environ, {"DATABRICKS_RUNTIME_VERSION": "14.3"}):
            assert _is_inside_databricks()


class TestDatabricksValidation:
    def test_validate_valid_source(
        self, databricks_backend: DatabricksBackend, databricks_source: Source
    ):
        with patch.dict(os.environ, {"DATABRICKS_TOKEN": "dapi123"}):
            issues = databricks_backend.validate_source(databricks_source, "/tmp")
            errors = [i for i in issues if i.level == "error"]
            assert len(errors) == 0

    def test_validate_missing_table(self, databricks_backend: DatabricksBackend):
        source = Source(
            name="bad",
            backend="databricks",
            table="placeholder",
            entity="doctor",
            timestamp_column="ts",
            columns=[],
        )
        source.table = None
        issues = databricks_backend.validate_source(source, "/tmp")
        assert any("Missing 'table'" in i.message for i in issues)

    def test_validate_missing_host_warns(
        self, databricks_backend: DatabricksBackend
    ):
        source = Source(
            name="no_host",
            backend="databricks",
            table="catalog.schema.table",
            entity="doctor",
            timestamp_column="ts",
            columns=[],
        )
        with patch.dict(os.environ, {}, clear=True):
            issues = databricks_backend.validate_source(source, "/tmp")
            warnings = [i for i in issues if i.level == "warning"]
            assert any("host" in i.message.lower() for i in warnings)

    def test_validate_missing_token_warns(
        self, databricks_backend: DatabricksBackend, databricks_source: Source
    ):
        with patch.dict(os.environ, {}, clear=True):
            issues = databricks_backend.validate_source(databricks_source, "/tmp")
            warnings = [i for i in issues if i.level == "warning"]
            assert any("TOKEN" in i.message for i in warnings)

    def test_validate_inside_databricks_no_token_needed(
        self, databricks_backend: DatabricksBackend, databricks_source: Source
    ):
        with patch.dict(
            os.environ, {"DATABRICKS_RUNTIME_VERSION": "14.3"}, clear=True
        ):
            issues = databricks_backend.validate_source(databricks_source, "/tmp")
            # No warning about token when inside Databricks
            token_warnings = [i for i in issues if "TOKEN" in i.message]
            assert len(token_warnings) == 0


class TestDatabricksCredentials:
    def test_get_credentials_from_source(
        self, databricks_backend: DatabricksBackend, databricks_source: Source
    ):
        with patch.dict(os.environ, {"DATABRICKS_TOKEN": "dapi123"}):
            host, wid, token = databricks_backend._get_credentials(databricks_source)
            assert host == "adb-123.azuredatabricks.net"
            assert wid == "abc123"
            assert token == "dapi123"

    def test_get_credentials_from_env(
        self, databricks_backend: DatabricksBackend
    ):
        source = Source(
            name="from_env",
            backend="databricks",
            table="catalog.schema.table",
            entity="doctor",
            timestamp_column="ts",
            columns=[],
        )
        env = {
            "DATABRICKS_HOST": "env-host.databricks.net",
            "DATABRICKS_WAREHOUSE_ID": "env-wid",
            "DATABRICKS_TOKEN": "env-token",
        }
        with patch.dict(os.environ, env):
            host, wid, token = databricks_backend._get_credentials(source)
            assert host == "env-host.databricks.net"
            assert wid == "env-wid"
            assert token == "env-token"

    def test_get_credentials_missing_host_raises(
        self, databricks_backend: DatabricksBackend
    ):
        source = Source(
            name="no_host",
            backend="databricks",
            table="catalog.schema.table",
            entity="doctor",
            timestamp_column="ts",
            columns=[],
        )
        with patch.dict(os.environ, {}, clear=True), pytest.raises(
            BackendError, match="host"
        ):
            databricks_backend._get_credentials(source)

    def test_get_credentials_missing_token_raises_outside(
        self, databricks_backend: DatabricksBackend, databricks_source: Source
    ):
        with patch.dict(os.environ, {}, clear=True), pytest.raises(
            BackendError, match="TOKEN"
        ):
            databricks_backend._get_credentials(databricks_source)
