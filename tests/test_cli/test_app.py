"""Tests for the CLI application."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from feature_forge.cli.app import app

runner = CliRunner()


class TestVersion:
    def test_version_flag(self):
        result = runner.invoke(app, ["-v"])
        assert result.exit_code == 0
        assert "feature-forge" in result.output


class TestInit:
    def test_init_creates_files(self, tmp_path: Path):
        result = runner.invoke(app, ["init", str(tmp_path / "new_repo")])
        assert result.exit_code == 0
        assert (tmp_path / "new_repo" / "entities.yml").exists()
        assert (tmp_path / "new_repo" / "sources.yml").exists()
        assert (tmp_path / "new_repo" / "features.yml").exists()

    def test_init_existing_dir(self, tmp_path: Path):
        # First init
        runner.invoke(app, ["init", str(tmp_path)])
        # Second init should warn
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert "already exist" in result.output

    def test_init_content_is_valid_yaml(self, tmp_path: Path):
        runner.invoke(app, ["init", str(tmp_path / "repo")])
        from feature_forge.registry.loader import load_registry

        registry = load_registry(tmp_path / "repo")
        assert len(registry.entities) == 1
        assert len(registry.sources) == 1
        assert len(registry.feature_views) == 1


class TestValidate:
    def test_validate_valid_repo(self, feature_repo: Path):
        result = runner.invoke(app, ["validate", "--repo", str(feature_repo)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_validate_invalid_repo(self, invalid_repo_path: Path):
        result = runner.invoke(app, ["validate", "--repo", str(invalid_repo_path)])
        assert result.exit_code == 1
        assert "error" in result.output.lower()

    def test_validate_nonexistent_repo(self, tmp_path: Path):
        result = runner.invoke(
            app, ["validate", "--repo", str(tmp_path / "nonexistent")]
        )
        assert result.exit_code == 1


class TestList:
    def test_list_entities(self, feature_repo: Path):
        result = runner.invoke(
            app, ["list", "entities", "--repo", str(feature_repo)]
        )
        assert result.exit_code == 0
        assert "customer" in result.output
        assert "merchant" in result.output

    def test_list_sources(self, feature_repo: Path):
        result = runner.invoke(
            app, ["list", "sources", "--repo", str(feature_repo)]
        )
        assert result.exit_code == 0
        assert "transactions" in result.output
        assert "parquet" in result.output

    def test_list_features(self, feature_repo: Path):
        result = runner.invoke(
            app, ["list", "features", "--repo", str(feature_repo)]
        )
        assert result.exit_code == 0
        assert "customer_transaction_features" in result.output

    def test_list_invalid_kind(self, feature_repo: Path):
        result = runner.invoke(
            app, ["list", "invalid", "--repo", str(feature_repo)]
        )
        assert result.exit_code == 1


class TestDescribe:
    def test_describe_feature_view(self, feature_repo: Path):
        result = runner.invoke(
            app,
            ["describe", "customer_transaction_features", "--repo", str(feature_repo)],
        )
        assert result.exit_code == 0
        assert "customer_transaction_features" in result.output
        # Rich may truncate long names, check prefix
        assert "transaction_co" in result.output
        assert "aggregation" in result.output

    def test_describe_passthrough_view(self, feature_repo: Path):
        result = runner.invoke(
            app,
            ["describe", "customer_profile_features", "--repo", str(feature_repo)],
        )
        assert result.exit_code == 0
        assert "customer_age" in result.output
        assert "passthrough" in result.output

    def test_describe_nonexistent(self, feature_repo: Path):
        result = runner.invoke(
            app,
            ["describe", "nonexistent_view", "--repo", str(feature_repo)],
        )
        assert result.exit_code == 1
        assert "not found" in result.output


class TestMaterialize:
    def test_materialize_to_default_path(self, feature_repo: Path):
        result = runner.invoke(
            app,
            [
                "materialize",
                "customer_transaction_features",
                "--start", "2025-01-05",
                "--end", "2025-01-07",
                "--entity-key", "customer_id",
                "--entity-values", "1,2",
                "--repo", str(feature_repo),
            ],
        )
        assert result.exit_code == 0
        assert "Materialized" in result.output

    def test_materialize_to_custom_path(self, feature_repo: Path, tmp_path: Path):
        output = tmp_path / "output.parquet"
        result = runner.invoke(
            app,
            [
                "materialize",
                "customer_transaction_features",
                "--start", "2025-01-05",
                "--end", "2025-01-07",
                "--entity-key", "customer_id",
                "--entity-values", "1",
                "--output", str(output),
                "--repo", str(feature_repo),
            ],
        )
        assert result.exit_code == 0
        assert output.exists()
