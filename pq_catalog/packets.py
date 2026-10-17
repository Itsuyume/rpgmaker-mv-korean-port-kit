"""Build bounded translation packets with deduplicated ordered context traces."""
from bisect import bisect_left
from typing import NotRequired, TypedDict

from .schema import Catalog, ContextRecord, Segment, TraceRecord
from .tokens import word_count


class PacketRow(TypedDict):
    protected: NotRequired[list[str]]
    id: str
    source: str
    source_sha256: str
    kind: str
    contexts: list[ContextRecord]


class Packet(TypedDict):
    schema_version: int
    group: int
    phase: str
    chunk: int
    rows: list[PacketRow]
    traces: dict[str, TraceRecord]
    stats: dict[str, int]


def context_slice(trace: TraceRecord, context: ContextRecord) -> dict[str, list[str]]:
    index = context["command_index"]
    if index is None:
        return dict(trace["entries"])
    indices = sorted(int(key) for key in trace["entries"])
    position = bisect_left(indices, index)
    return {str(i): trace["entries"][str(i)] for i in indices[max(0, position - 2):position + 3]}


def packet(catalog: Catalog, segments: list[Segment], group: int, chunk: int, phase: str = "core") -> Packet:
    traces: dict[str, TraceRecord] = {}
    rows: list[PacketRow] = []
    for segment in segments:
        rows.append({"id": segment["id"], "source": segment["source"],
                     "source_sha256": segment["source_sha256"], "kind": segment["kind"],
                     "contexts": segment["contexts"]})
        if "protected" in segment:
            rows[-1]["protected"] = segment["protected"]
        for context in segment["contexts"]:
            key = context["trace"]
            original = catalog["traces"][key]
            target = traces.setdefault(key, {**original, "entries": {}})
            target["entries"].update(context_slice(original, context))
    source_words = sum(segment["word_count"] for segment in segments)
    context_words = sum(word_count(text) for trace in traces.values() for texts in trace["entries"].values() for text in texts)
    return {"schema_version": 1, "group": group, "phase": phase, "chunk": chunk,
            "rows": rows, "traces": traces, "stats": {"items": len(rows), "source_words": source_words,
            "context_words": context_words, "total_words": source_words + context_words}}


def bounded_packets(catalog: Catalog, segments: list[Segment], group: int,
                    max_items: int = 180, max_words: int = 2500, phase: str = "core") -> list[Packet]:
    if max_items < 1 or max_words < 1:
        raise ValueError("Packet limits must be positive.")
    result: list[Packet] = []
    current: list[Segment] = []
    for segment in segments:
        candidate = packet(catalog, [*current, segment], group, len(result) + 1, phase)
        if current and (len(candidate["rows"]) > max_items or candidate["stats"]["total_words"] > max_words):
            result.append(packet(catalog, current, group, len(result) + 1, phase))
            current = []
            candidate = packet(catalog, [segment], group, len(result) + 1, phase)
        if candidate["stats"]["total_words"] > max_words:
            raise ValueError("A single unit and its bounded context exceed the word limit: " + segment["id"])
        current.append(segment)
    if current:
        result.append(packet(catalog, current, group, len(result) + 1, phase))
    return result
