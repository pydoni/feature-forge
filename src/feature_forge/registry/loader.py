"""Load and parse feature registry YAML files from a repository directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from feature_forge.exceptions import RegistryError
from feature_forge.registry.models import (
    Entity,
    FeatureRegistry,
    FeatureView,
    Source,
)


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise RegistryError(f"Expected a YAML mapping in {path}, got {type(data).__name__}")
        return data
    except yaml.YAMLError as e:
        raise RegistryError(f"Failed to parse YAML file {path}: {e}") from e


def _parse_entities(data: dict[str, Any]) -> list[Entity]:
    raw = data.get("entities", [])
    if not isinstance(raw, list):
        raise RegistryError("'entities' must be a list")
    return [Entity(**item) for item in raw]


def _parse_sources(data: dict[str, Any]) -> list[Source]:
    raw = data.get("sources", [])
    if not isinstance(raw, list):
        raise RegistryError("'sources' must be a list")
    return [Source(**item) for item in raw]


def _parse_feature_views(data: dict[str, Any]) -> list[FeatureView]:
    raw = data.get("feature_views", [])
    if not isinstance(raw, list):
        raise RegistryError("'feature_views' must be a list")
    return [FeatureView(**item) for item in raw]


def load_registry(repo_path: str | Path) -> FeatureRegistry:
    """Load a complete feature registry from a directory of YAML files.

    Discovers all .yml and .yaml files in the repo directory (non-recursive),
    parses entities, sources, and feature_views from each, and merges them
    into a single FeatureRegistry.
    """
    repo = Path(repo_path)
    if not repo.is_dir():
        raise RegistryError(f"Feature repo path does not exist or is not a directory: {repo}")

    yaml_files = sorted(repo.glob("*.yml")) + sorted(repo.glob("*.yaml"))
    if not yaml_files:
        raise RegistryError(f"No YAML files found in {repo}")

    entities: list[Entity] = []
    sources: list[Source] = []
    feature_views: list[FeatureView] = []
    engine = "duckdb"

    for path in yaml_files:
        data = _load_yaml(path)
        try:
            entities.extend(_parse_entities(data))
            sources.extend(_parse_sources(data))
            feature_views.extend(_parse_feature_views(data))
            if "engine" in data:
                engine = data["engine"]
        except Exception as e:
            raise RegistryError(f"Error parsing {path.name}: {e}") from e

    return FeatureRegistry(
        entities=entities,
        sources=sources,
        feature_views=feature_views,
        engine=engine,
    )
