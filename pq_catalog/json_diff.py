"""Prove that only explicitly planned display leaves changed."""
from .model import JsonPath, JsonValue


def assert_allowed_diff(before: JsonValue, after: JsonValue,
                        expected: dict[JsonPath, str], path: JsonPath = ()) -> None:
    if type(before) is not type(after):
        raise ValueError("JSON value type changed outside the string contract: " + str(path))
    if isinstance(before, dict) and isinstance(after, dict):
        if list(before) != list(after):
            raise ValueError("JSON object keys/order changed: " + str(path))
        for key in before:
            assert_allowed_diff(before[key], after[key], expected, path + (key,))
        return
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            raise ValueError("JSON array length changed: " + str(path))
        for index, value in enumerate(before):
            assert_allowed_diff(value, after[index], expected, path + (index,))
        return
    if path in expected:
        if not isinstance(before, str) or after != expected[path]:
            raise ValueError("Planned display replacement mismatch: " + str(path))
    elif before != after:
        raise ValueError("Non-display field changed: " + str(path))
