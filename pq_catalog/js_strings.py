"""Ordinary JavaScript quoted string codec; never evaluate expressions."""
import re

ESCAPES = {"b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v", "0": "\0"}


def escape(text: str, index: int) -> tuple[str, int]:
    char = text[index]
    if char in ESCAPES:
        if char == "0" and index + 1 < len(text) and text[index + 1].isdigit():
            raise ValueError("Legacy octal JS escapes are outside the audited codec.")
        return ESCAPES[char], index + 1
    if char in "\r\n":
        return "", index + (2 if text[index:index + 2] == "\r\n" else 1)
    if char in "xu":
        width = 2 if char == "x" else 4
        digits = text[index + 1:index + 1 + width]
        if not re.fullmatch("[0-9a-fA-F]{" + str(width) + "}", digits):
            raise ValueError("Malformed JavaScript hex escape.")
        return chr(int(digits, 16)), index + width + 1
    if char.isdigit():
        raise ValueError("Legacy numeric JS escapes are outside the audited codec.")
    return char, index + 1


def decode_literal(literal: bytes) -> str:
    text = literal.decode("utf-8")
    if len(text) < 2 or text[0] not in "\"'" or text[-1] != text[0]:
        raise ValueError("Expected one complete ordinary JS quoted literal.")
    result: list[str] = []
    index = 1
    while index < len(text) - 1:
        char = text[index]
        if char == "\\":
            if index + 1 >= len(text) - 1:
                raise ValueError("Trailing JS escape before closing quote.")
            char, index = escape(text, index + 1)
        else:
            if char == text[0] or char in "\r\n":
                raise ValueError("Unescaped quote/newline inside JS literal.")
            index += 1
        result.append(char)
    value = "".join(result)
    return value.encode("utf-16", "surrogatepass").decode("utf-16")


def encode_literal(text: str, quote: str) -> bytes:
    if quote not in {"'", '"'}:
        raise ValueError("Unsupported ordinary JS quote.")
    escaped: list[str] = []
    controls = {value: "\\" + key for key, value in ESCAPES.items() if key != "0"}
    for char in text:
        if char in {quote, "\\"}:
            escaped.append("\\" + char)
        elif char in controls:
            escaped.append(controls[char])
        elif ord(char) < 32 or char in {"\u2028", "\u2029"}:
            escaped.append("\\u" + format(ord(char), "04x"))
        else:
            escaped.append(char)
    return (quote + "".join(escaped) + quote).encode("utf-8")
