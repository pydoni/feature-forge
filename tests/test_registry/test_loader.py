"""Tests for the YAML registry loader."""

from pathlib import Path

import pytest

from feature_forge.exceptions import RegistryError
from feature_forge.registry.loader import load_registry


class TestLoadRegistry:
    def test_load_valid_repo(self, valid_repo_path: Path):
        registry = load_registry(valid_repo_path)
        assert len(registry.entities) == 2
        assert len(registry.sources) == 2
        assert len(registry.feature_views) == 2

    def test_entity_names(self, valid_repo_path: Path):
        registry = load_registry(valid_repo_path)
        names = {e.name for e in registry.entities}
        assert names == {"customer", "merchant"}

    def test_source_names(self, valid_repo_path: Path):
        registry = load_registry(valid_repo_path)
        names = {s.name for s in registry.sources}
        assert names == {"transactions", "user_profiles"}

    def test_feature_view_names(self, valid_repo_path: Path):
        registry = load_registry(valid_repo_path)
        names = {fv.name for fv in registry.feature_views}
        assert names == {"customer_transaction_features", "customer_profile_features"}

    def test_features_loaded(self, valid_repo_path: Path):
        registry = load_registry(valid_repo_path)
        txn_fv = registry.get_feature_view("customer_transaction_features")
        assert txn_fv is not None
        assert len(txn_fv.features) == 3
        feature_names = {f.name for f in txn_fv.features}
        assert "transaction_count_7d" in feature_names
        assert "avg_transaction_amount_30d" in feature_names

    def test_default_engine(self, valid_repo_path: Path):
        registry = load_registry(valid_repo_path)
        assert registry.engine == "duckdb"

    def test_nonexistent_dir(self, tmp_path: Path):
        with pytest.raises(RegistryError, match="does not exist"):
            load_registry(tmp_path / "nonexistent")

    def test_empty_dir(self, tmp_path: Path):
        with pytest.raises(RegistryError, match="No YAML files"):
            load_registry(tmp_path)

    def test_invalid_yaml(self, tmp_path: Path):
        (tmp_path / "bad.yml").write_text("{\n  bad: [unclosed\n")
        with pytest.raises(RegistryError, match="Failed to parse"):
            load_registry(tmp_path)

    def test_non_dict_yaml(self, tmp_path: Path):
        (tmp_path / "list.yml").write_text("- item1\n- item2\n")
        with pytest.raises(RegistryError, match="Expected a YAML mapping"):
            load_registry(tmp_path)

    def test_empty_yaml_file(self, tmp_path: Path):
        (tmp_path / "empty.yml").write_text("")
        # Empty YAML should parse to empty registry
        registry = load_registry(tmp_path)
        assert len(registry.entities) == 0

    def test_loads_invalid_repo(self, invalid_repo_path: Path):
        # Should load (parsing works), validation is separate
        registry = load_registry(invalid_repo_path)
        assert len(registry.feature_views) == 1
