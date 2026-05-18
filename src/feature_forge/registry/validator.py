"""Cross-reference validation for the feature registry."""

from __future__ import annotations

from dataclasses import dataclass

from feature_forge.backends.base import ValidationIssue
from feature_forge.backends.factory import get_backend
from feature_forge.registry.models import FeatureRegistry
from feature_forge.types import AggFunction


@dataclass
class RegistryValidationResult:
    """Result of validating a feature registry."""

    issues: list[ValidationIssue]

    @property
    def is_valid(self) -> bool:
        return not any(i.level == "error" for i in self.issues)

    def __bool__(self) -> bool:
        return self.is_valid


def validate_registry(registry: FeatureRegistry, repo_path: str) -> RegistryValidationResult:
    """Validate the feature registry for cross-reference consistency and source accessibility."""
    issues: list[ValidationIssue] = []

    entity_names = {e.name for e in registry.entities}
    source_names = {s.name for s in registry.sources}
    source_map = {s.name: s for s in registry.sources}

    # 1. Check for duplicate names
    _check_duplicates(issues, [e.name for e in registry.entities], "Entity")
    _check_duplicates(issues, [s.name for s in registry.sources], "Source")
    _check_duplicates(issues, [fv.name for fv in registry.feature_views], "FeatureView")

    # 2. Validate sources reference valid entities
    for source in registry.sources:
        if source.entity not in entity_names:
            issues.append(
                ValidationIssue(
                    source.name,
                    f"Source references unknown entity '{source.entity}'",
                )
            )

    # 3. Validate feature views
    for fv in registry.feature_views:
        # Entity reference
        if fv.entity not in entity_names:
            issues.append(
                ValidationIssue(fv.name, f"FeatureView references unknown entity '{fv.entity}'")
            )

        # Source reference
        if fv.source not in source_names:
            issues.append(
                ValidationIssue(fv.name, f"FeatureView references unknown source '{fv.source}'")
            )
            continue

        source = source_map[fv.source]

        # Entity consistency: feature view entity must match source entity
        if source.entity != fv.entity:
            issues.append(
                ValidationIssue(
                    fv.name,
                    f"FeatureView entity '{fv.entity}' does not match "
                    f"source '{source.name}' entity '{source.entity}'",
                )
            )

        source_col_names = source.get_column_names()

        # Validate each feature
        for feature in fv.features:
            if feature.column is not None and feature.column not in source_col_names:
                    issues.append(
                        ValidationIssue(
                            fv.name,
                            f"Feature '{feature.name}' references column '{feature.column}' "
                            f"not found in source '{source.name}'. "
                            f"Available: {source_col_names}",
                        )
                    )

            if feature.aggregation is not None:
                # Aggregation: column must exist in source
                if feature.aggregation.column not in source_col_names:
                    issues.append(
                        ValidationIssue(
                            fv.name,
                            f"Feature '{feature.name}' aggregation references column "
                            f"'{feature.aggregation.column}' not found in source '{source.name}'. "
                            f"Available: {source_col_names}",
                        )
                    )

                # Count always produces int64
                if feature.aggregation.function in (
                    AggFunction.COUNT,
                    AggFunction.COUNT_DISTINCT,
                ) and feature.dtype != "int64":
                    issues.append(
                        ValidationIssue(
                            fv.name,
                            f"Feature '{feature.name}' uses {feature.aggregation.function} "
                            f"but dtype is '{feature.dtype}' (expected 'int64')",
                            level="warning",
                        )
                    )

        # Check for duplicate feature names within a view
        _check_duplicates(
            issues,
            [f.name for f in fv.features],
            f"Feature in '{fv.name}'",
        )

    # 4. Validate source backends (file existence, schema match)
    for source in registry.sources:
        try:
            backend = get_backend(source.backend)
            backend_issues = backend.validate_source(source, repo_path)
            issues.extend(backend_issues)
        except Exception as e:
            issues.append(
                ValidationIssue(source.name, f"Backend validation error: {e}")
            )

    return RegistryValidationResult(issues=issues)


def _check_duplicates(
    issues: list[ValidationIssue], names: list[str], kind: str
) -> None:
    seen: set[str] = set()
    for name in names:
        if name in seen:
            issues.append(ValidationIssue(name, f"Duplicate {kind} name: '{name}'"))
        seen.add(name)
