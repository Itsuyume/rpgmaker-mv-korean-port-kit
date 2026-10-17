"""MV controls, audited YEP namebox shells, newlines and numeric literals."""
from __future__ import annotations

from collections.abc import Iterator
import re

TOKEN_VERSION = "mv-english-namebox-shell-v1"
NAMEBOX = r"(?P<namebox>\\[Nn](?:[1-5CcRr])?<[^>\r\n]*>)"
CONTROL = r"\\(?:[A-Za-z]+(?:\[[^\]\r\n]*\]|<[^>\r\n]*>)?|[{}.$|!><^\\])"
HTML = r"</?[A-Za-z][A-Za-z0-9:_-]*(?:\s[^<>\r\n]*)?/?>"
STRUCTURAL = re.compile(NAMEBOX + "|" + CONTROL + "|" + HTML + r"|%\d+|\r?\n|\u3000|[♥♡☆]|\uffff")
NUMBER = re.compile(r"[+-]?\d+(?:\.\d+)?")
WORD = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")


def spans(text: str, offset: int = 0) -> Iterator[tuple[int, int, str]]:
    for match in STRUCTURAL.finditer(text):
        if match.group("namebox") is None:
            yield offset + match.start(), offset + match.end(), match.group()
            continue
        value = match.group()
        opening = value.index("<") + 1
        yield offset + match.start(), offset + match.start() + opening, value[:opening]
        yield from spans(value[opening:-1], offset + match.start() + opening)
        yield offset + match.end() - 1, offset + match.end(), ">"


def extract_tokens(text: str) -> list[str]:
    return [token for _, _, token in spans(text)]


def visible_text(text: str) -> str:
    result, end = [], 0
    for start, stop, _ in spans(text):
        result.append(text[end:start])
        end = stop
    result.append(text[end:])
    return "".join(result)


def has_language(text: str) -> bool:
    return any(character.isalpha() for character in visible_text(text))


def word_count(text: str) -> int:
    return len(WORD.findall(visible_text(text)))


def assert_preserved(source: str, target: str, protected: list[str] | None = None) -> None:
    if protected:
        for token in set(protected):
            if source.count(token) != target.count(token):
                raise ValueError("Audited opaque token count changed.")
        source, _ = opaque_parts(source, protected)
        target, _ = opaque_parts(target, protected)
    if extract_tokens(source) != extract_tokens(target):
        raise ValueError("Control/format/newline token sequence changed.")
    if NUMBER.findall(visible_text(source)) != NUMBER.findall(visible_text(target)):
        raise ValueError("Numeric literal sequence changed.")
    # Whitespace is never trimmed or normalized. Intentional Korean fragment
    # spacing is authored by the translator, not repaired by the applicator.


def opaque_parts(text: str, protected: list[str]) -> tuple[str, list[str]]:
    """Mask audited opaque blocks and return their original ordered values."""
    cursor = 0
    result: list[str] = []
    found: list[str] = []
    for token in protected:
        if not token:
            raise ValueError("An empty opaque token is invalid.")
        index = text.find(token, cursor)
        if index < 0:
            raise ValueError("An audited opaque expression/command changed order or content.")
        result.extend((text[cursor:index], "\uffff"))
        found.append(token)
        cursor = index + len(token)
    result.append(text[cursor:])
    return "".join(result), found
