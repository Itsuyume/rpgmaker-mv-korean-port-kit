"""Nested plugin JSON/string codecs, grouping changes before re-encoding."""
from copy import deepcopy
import json
import re

from .js_spans import encode_target, selected_literal
from .json_store import array_value, decode_json, decode_prefix, digest_text, get_path, object_value, set_path, string_value
from .model import JsonPath, JsonValue
from .plugin_contract import Step, Target


def parse_plugins(data: bytes) -> tuple[str, list[JsonValue], str]:
    text = data.decode("utf-8")
    matches = list(re.finditer(r"(?m)^[ \t]*var\s+\$plugins\s*=\s*", text))
    if len(matches) != 1:
        raise ValueError("Expected one literal $plugins JSON assignment.")
    start = matches[0].end()
    document, end = decode_prefix(text, start)
    suffix = text[end:]
    if suffix.strip() != ";":
        raise ValueError("Unexpected code after the literal $plugins array.")
    return text[:start], array_value(document), suffix


def verify_plugin(document: JsonValue, target: Target) -> None:
    if target.plugin_index is None or target.plugin_name is None or target.expected_status is None:
        raise ValueError("Plugin selector lacks name/index/status guards.")
    row = object_value(array_value(document)[target.plugin_index])
    if row["name"] != target.plugin_name or row["status"] is not target.expected_status:
        raise ValueError("Audited plugin name/status mismatch.")


def terminal_source(value: str, step: Step, target: Target) -> str:
    if step.codec == "raw":
        source = value
    elif step.codec == "json-string":
        source = string_value(decode_json(value))
    elif step.codec == "js-expression":
        if digest_text(value) != target.expression_sha256:
            raise ValueError("Audited JS parameter expression hash mismatch.")
        source = selected_literal(value.encode("utf-8"), target, "utf8-bytes-of-decoded-parameter")
    else:
        raise ValueError("JSON container cannot be a terminal display string.")
    if source != target.source:
        raise ValueError("Audited plugin display source mismatch.")
    return source


def selected_text(document: JsonValue, target: Target) -> str:
    verify_plugin(document, target)
    current = document
    for index, step in enumerate(target.steps):
        value = string_value(get_path(current, step.path))
        if index == len(target.steps) - 1:
            return terminal_source(value, step, target)
        if step.codec != "json":
            raise ValueError("Only JSON containers may have nested selectors.")
        current = decode_json(value)
        if not isinstance(current, (dict, list)):
            raise ValueError("Nested plugin container is not an object/array.")
    raise ValueError("No plugin selector.")


def terminal_value(value: str, step: Step, target: Target, text: str) -> str:
    if terminal_source(value, step, target) == text:
        return value
    if step.codec == "raw": return text
    if step.codec == "json-string": return json.dumps(text, ensure_ascii=False)
    if step.codec != "js-expression" or target.span is None:
        raise ValueError("Unsupported terminal plugin replacement.")
    data = value.encode("utf-8")
    return (data[:target.span.start] + encode_target(target, text) + data[target.span.end:]).decode("utf-8")


def apply_nested(document: JsonValue, changes: list[tuple[Target, str]], level: int = 0) -> JsonValue:
    result = deepcopy(document)
    grouped: dict[tuple[JsonPath, str], list[tuple[Target, str]]] = {}
    for target, text in changes:
        step = target.steps[level]
        grouped.setdefault((step.path, step.codec), []).append((target, text))
    paths = [path for path, _ in grouped]
    if len(paths) != len(set(paths)):
        raise ValueError("One plugin path declares inconsistent codecs.")
    for (path, codec), values in grouped.items():
        original = string_value(get_path(result, path))
        if codec == "json":
            if any(level + 1 >= len(target.steps) for target, _ in values):
                raise ValueError("Missing nested selector after a JSON container.")
            decoded = decode_json(original)
            updated = apply_nested(decoded, values, level + 1)
            replacement = original if decoded == updated else json.dumps(updated, ensure_ascii=False)
        else:
            if len(values) != 1 or level != len(values[0][0].steps) - 1:
                raise ValueError("Duplicate terminal selector or unexpected nested steps.")
            replacement = terminal_value(original, values[0][0].steps[level], *values[0])
        set_path(result, path, replacement)
    return result
