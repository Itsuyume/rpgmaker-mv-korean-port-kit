"""Guarded JS byte spans and template opaque blocks; no execution/eval."""
import re

from .js_strings import decode_literal, encode_literal
from .json_store import digest_bytes, digest_text
from .plugin_contract import Target
from .tokens import assert_preserved, opaque_parts


def literal_bytes(data: bytes, target: Target, unit: str) -> bytes:
    span = target.span
    if span is None or span.unit != unit or span.end > len(data):
        raise ValueError("JS span unit/range does not match its audited document.")
    literal = data[span.start:span.end]
    if target.literal_sha256 is None or digest_bytes(literal) != target.literal_sha256:
        raise ValueError("Audited JS literal hash mismatch.")
    if not literal.startswith(span.quote.encode()) or not literal.endswith(span.quote.encode()):
        raise ValueError("Audited JS quote mismatch.")
    return literal


def selected_literal(data: bytes, target: Target, unit: str) -> str:
    literal = literal_bytes(data, target, unit)
    source = literal[1:-1].decode("utf-8") if target.document_codec == "js-template-literal" else decode_literal(literal)
    if source != target.source or digest_text(source) != target.source_sha256:
        raise ValueError("Audited decoded JS source mismatch.")
    return source


def template_blocks(source: str, expressions: tuple[str, ...]) -> list[str]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    for expression in expressions:
        value = "${" + expression + "}"
        index = source.find(value, cursor)
        if index < 0:
            raise ValueError("Audited template expression missing or reordered.")
        spans.append((index, index + len(value)))
        cursor = index + len(value)
    if source.count("${") != len(expressions):
        raise ValueError("Undeclared template interpolation.")
    for pattern in (r"<pre\b[^>]*>[\s\S]*?</pre>", r"\b[A-Za-z0-9_-]+\.(?:app|exe|json|js|zip)\b"):
        spans.extend((match.start(), match.end()) for match in re.finditer(pattern, source))
    selected: list[tuple[int, int]] = []
    for start, end in sorted(spans, key=lambda item: (item[0], -item[1])):
        if selected and start < selected[-1][1]:
            if end > selected[-1][1]:
                raise ValueError("Overlapping audited template blocks.")
            continue
        selected.append((start, end))
    return [source[start:end] for start, end in selected]


def encode_target(target: Target, text: str) -> bytes:
    if target.span is None:
        raise ValueError("JS target requires a span.")
    if target.document_codec != "js-template-literal":
        return encode_literal(text, target.span.quote)
    blocks = template_blocks(target.source, target.expressions)
    assert_preserved(target.source, text, blocks)
    masked, _ = opaque_parts(text, blocks)
    original, _ = opaque_parts(target.source, blocks)
    if "`" in masked or masked.count("${") != original.count("${"):
        raise ValueError("New template delimiter/interpolation is forbidden.")
    if re.findall(r"\\[\s\S]", masked) != re.findall(r"\\[\s\S]", original):
        raise ValueError("Static template escape bytes changed.")
    return ("`" + text + "`").encode("utf-8")


def replace_spans(data: bytes, changes: list[tuple[Target, str]]) -> bytes:
    replacements: list[tuple[int, int, bytes]] = []
    for target, text in changes:
        original = selected_literal(data, target, "utf8-bytes")
        if text == original:
            continue
        if target.span is None:
            raise ValueError("Missing JS span.")
        replacements.append((target.span.start, target.span.end, encode_target(target, text)))
    replacements.sort()
    if any(right[0] < left[1] for left, right in zip(replacements, replacements[1:])):
        raise ValueError("Audited JS spans overlap.")
    result = data
    for start, end, value in reversed(replacements):
        result = result[:start] + value + result[end:]
    return result
