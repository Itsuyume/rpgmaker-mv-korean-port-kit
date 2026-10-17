"""Validate flat ID-to-Korean shards without changing their authored text."""
from dataclasses import dataclass
from pathlib import Path

from .catalog import stable_key
from .json_store import array_value, object_value, read_json, string_value
from .schema import Catalog, Segment
from .tokens import assert_preserved


@dataclass(frozen=True)
class ValidationResult:
    expected: int
    saved: int
    pending: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.pending and not self.errors


def plan_ids(path: Path) -> list[str]:
    plan = object_value(read_json(path))
    ids = [string_value(item) for item in array_value(plan["ids"])]
    if len(ids) != len(set(ids)) or plan["ids_sha256"] != stable_key(ids):
        raise ValueError("Plan IDs are duplicated or their immutable hash changed.")
    return ids


def load_shards(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Shards must be a regular directory.")
    merged: dict[str, str] = {}
    for path in sorted(root.glob("*.json")):
        if path.is_symlink():
            raise ValueError("Shard symlinks are forbidden.")
        for identifier, raw in object_value(read_json(path)).items():
            if identifier in merged:
                raise ValueError("Duplicate shard ID: " + identifier)
            merged[identifier] = string_value(raw)
    return merged


def validate(catalog: Catalog, ids: list[str], translations: dict[str, str]) -> ValidationResult:
    selected = {row["id"]: row for row in catalog["segments"] if row["translate"]}
    if len(ids) != len(set(ids)) or any(identifier not in selected for identifier in ids):
        raise ValueError("Plan contains duplicate, unknown or preserved IDs.")
    expected = set(ids)
    errors = ["Unexpected shard ID: " + identifier for identifier in sorted(set(translations) - expected)]
    for identifier in ids:
        if identifier not in translations:
            continue
        target = translations[identifier]
        if not target.strip():
            errors.append("Empty translation: " + identifier)
            continue
        try:
            assert_preserved(selected[identifier]["source"], target, selected[identifier].get("protected", []))
        except ValueError as error:
            errors.append(identifier + ": " + str(error))
    missing = tuple(identifier for identifier in ids if identifier not in translations)
    return ValidationResult(len(ids), len(expected & translations.keys()), missing, tuple(errors))


def pending_rows(catalog: Catalog, result: ValidationResult) -> list[Segment]:
    pending = set(result.pending)
    return [row for row in catalog["segments"] if row["id"] in pending]
