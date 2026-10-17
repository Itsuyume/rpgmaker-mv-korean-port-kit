"""Compare every decoded plugin value, allowing only audited display leaves."""
from .json_diff import assert_allowed_diff
from .json_store import decode_json, get_path, string_value
from .model import JsonPath, JsonValue
from .plugin_codecs import terminal_value
from .plugin_contract import Target


def assert_nested_diff(before: JsonValue, after: JsonValue,
                       changes: list[tuple[Target, str]], level: int = 0) -> None:
    grouped: dict[JsonPath, list[tuple[Target, str]]] = {}
    for target, text in changes:
        grouped.setdefault(target.steps[level].path, []).append((target, text))
    allowed = {path: string_value(get_path(after, path)) for path in grouped}
    assert_allowed_diff(before, after, allowed)
    for path, selected in grouped.items():
        step = selected[0][0].steps[level]
        if any(target.steps[level].codec != step.codec for target, _ in selected):
            raise ValueError("One decoded plugin path has inconsistent codecs.")
        original, updated = string_value(get_path(before, path)), string_value(get_path(after, path))
        if step.codec == "json":
            assert_nested_diff(decode_json(original), decode_json(updated), selected, level + 1)
        elif len(selected) != 1:
            raise ValueError("Duplicate audited terminal plugin path.")
        elif updated != terminal_value(original, step, *selected[0]):
            raise ValueError("Decoded plugin display replacement differs from plan.")
