"""Serialized catalog contract shared by grouping, validation and application."""
from typing import NotRequired, TypedDict


class LocationRecord(TypedDict):
    file: str
    path: list[str | int]
    source_sha256: str
    role: str


class ContextRecord(TypedDict):
    trace: str
    command_index: int | None
    face_name: str | None
    choices: list[str]
    composition: str | None


class TraceRecord(TypedDict):
    file: str
    owner_path: list[str | int]
    owner_name: str
    entries: dict[str, list[str]]


class Segment(TypedDict):
    protected: NotRequired[list[str]]
    id: str
    source: str
    source_sha256: str
    kind: str
    translate: bool
    preserve_reason: str | None
    word_count: int
    locations: list[LocationRecord]
    contexts: list[ContextRecord]


class CatalogStats(TypedDict):
    units: int
    translate: int
    preserve: int
    words: int
    locations: int
    by_kind: dict[str, int]


class Catalog(TypedDict):
    audit_spec_sha256: NotRequired[str]
    schema_version: int
    scope: str
    token_version: str
    source_manifest_sha256: str
    source_files: dict[str, str]
    glossary_sha256: str
    segments: list[Segment]
    traces: dict[str, TraceRecord]
    stats: CatalogStats
