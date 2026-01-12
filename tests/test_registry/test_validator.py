"""Tests for the registry cross-reference validator."""

from pathlib import Path

from feature_forge.registry.loader import load_registry
from feature_forge.registry.validator import validate_registry


class TestValidateRegistry:
    def test_valid_repo_with_data(self, feature_repo: Path):
        registry = load_registry(feature_repo)
        result = validate_registry(registry, str(feature_repo))
        errors = [i for i in result.issues if i.level == "error"]
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert result.is_valid

    def test_invalid_repo_has_errors(self, invalid_repo_path: Path):
        registry = load_registry(invalid_repo_path)
        result = validate_registry(registry, str(invalid_repo_path))
        assert not result.is_valid
        error_messages = [i.message for i in result.issues if i.level == "error"]
        # Should detect: unknown entity, unknown source, missing parquet
        assert any("unknown entity" in m for m in error_messages)
        assert any("unknown source" in m for m in error_messages)

    def test_detects_missing_parquet(self, feature_repo: Path):
        # Modify a source to point to nonexistent file
        sources_yml = feature_repo / "sources.yml"
        content = sources_yml.read_text()
        content = content.replace(
            "data/transactions.parquet", "data/nonexistent.parquet"
        )
        sources_yml.write_text(content)

        registry = load_registry(feature_repo)
        result = validate_registry(registry, str(feature_repo))
        error_messages = [i.message for i in result.issues if i.level == "error"]
        assert any("not found" in m for m in error_messages)

    def test_detects_missing_columns_in_parquet(self, feature_repo: Path):
        # Add a column declaration that doesn't exist in the parquet
        sources_yml = feature_repo / "sources.yml"
        content = sources_yml.read_text()
        content = content.replace(
            "- { name: amount, dtype: float64 }",
            "- { name: amount, dtype: float64 }\n      - { name: fake_column, dtype: varchar }",
        )
        sources_yml.write_text(content)

        registry = load_registry(feature_repo)
        result = validate_registry(registry, str(feature_repo))
        error_messages = [i.message for i in result.issues if i.level == "error"]
        assert any("fake_column" in m for m in error_messages)

    def test_detects_duplicate_entity_names(self, tmp_path: Path):
        (tmp_path / "entities.yml").write_text(
            "entities:\n"
            "  - name: customer\n    join_keys: [id]\n"
            "  - name: customer\n    join_keys: [id]\n"
        )
        registry = load_registry(tmp_path)
        result = validate_registry(registry, str(tmp_path))
        error_messages = [i.message for i in result.issues]
        assert any("Duplicate" in m for m in error_messages)

    def test_detects_entity_source_mismatch(self, feature_repo: Path):
        # Change feature view entity to mismatch source
        features_yml = feature_repo / "features.yml"
        content = features_yml.read_text()
        content = content.replace(
            "entity: customer\n    source: user_profiles",
            "entity: merchant\n    source: user_profiles",
        )
        features_yml.write_text(content)

        registry = load_registry(feature_repo)
        result = validate_registry(registry, str(feature_repo))
        error_messages = [i.message for i in result.issues if i.level == "error"]
        assert any("does not match" in m for m in error_messages)

    def test_detects_feature_referencing_nonexistent_column(self, feature_repo: Path):
        features_yml = feature_repo / "features.yml"
        content = features_yml.read_text()
        content = content.replace("column: age", "column: nonexistent")
        features_yml.write_text(content)

        registry = load_registry(feature_repo)
        result = validate_registry(registry, str(feature_repo))
        error_messages = [i.message for i in result.issues if i.level == "error"]
        assert any("nonexistent" in m for m in error_messages)

    def test_bool_conversion(self, feature_repo: Path):
        registry = load_registry(feature_repo)
        result = validate_registry(registry, str(feature_repo))
        assert bool(result) is True
