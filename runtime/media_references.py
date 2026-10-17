"""Static, literal media paths only. This does not claim event reachability."""

import json
from pathlib import Path
import re


AUDIO_CODES = {241: "bgm", 245: "bgs", 249: "me", 250: "se"}
YSP_CALL = re.compile(r"\bysp\.VideoPlayer\.(?:newVideo|loadVideo)\s*\(")
YSP_LITERAL = re.compile(r"\bysp\.VideoPlayer\.(?:newVideo|loadVideo)\s*\(\s*(['\"])([^'\"\r\n]+)\1\s*[,)]")


def references_in_value(value: object, audio_extension: str) -> list[str]:
    paths = []
    if isinstance(value, str):
        paths.extend("movies/" + match[1] for match in YSP_LITERAL.findall(value))
        return paths
    if not isinstance(value, dict):
        return paths
    parameters = value.get("parameters")
    if isinstance(parameters, list) and parameters:
        if value.get("code") == 261 and isinstance(parameters[0], str) and parameters[0]:
            paths.append("movies/" + parameters[0] + ".webm")
        category = AUDIO_CODES.get(value.get("code"))
        if category and isinstance(parameters[0], dict) and parameters[0].get("name"):
            paths.append(f"audio/{category}/{parameters[0]['name']}{audio_extension}")
    for category, flag in (("bgm", "autoplayBgm"), ("bgs", "autoplayBgs")):
        audio = value.get(category)
        if value.get(flag) and isinstance(audio, dict) and audio.get("name"):
            paths.append(f"audio/{category}/{audio['name']}{audio_extension}")
    return paths


def walk_json(document: object):
    pending = [("", document)]
    while pending:
        pointer, value = pending.pop()
        yield pointer, value
        if isinstance(value, dict):
            pending.extend((pointer + "/" + str(key), item) for key, item in value.items())
        elif isinstance(value, list):
            pending.extend((pointer + "/" + str(index), item) for index, item in enumerate(value))


def system_audio(system: dict, extension: str) -> list[str]:
    paths = []
    for key, category in (("titleBgm", "bgm"), ("battleBgm", "bgm"),
                          ("victoryMe", "me"), ("defeatMe", "me")):
        audio = system.get(key)
        if isinstance(audio, dict) and audio.get("name"):
            paths.append(f"audio/{category}/{audio['name']}{extension}")
    for audio in system.get("sounds", []):
        if audio.get("name"):
            paths.append(f"audio/se/{audio['name']}{extension}")
    for vehicle in ("boat", "ship", "airship"):
        audio = system.get(vehicle, {}).get("bgm", {})
        if audio.get("name"):
            paths.append(f"audio/bgm/{audio['name']}{extension}")
    return paths


def audit_references(www: Path, encrypted_audio: bool) -> dict:
    extension = ".rpgmvo" if encrypted_audio else ".ogg"
    references: dict[str, list[str]] = {}
    dynamic_ysp = []
    for file in sorted((www / "data").glob("*.json")):
        document = json.loads(file.read_text(encoding="utf-8-sig"))
        for pointer, value in walk_json(document):
            for target in references_in_value(value, extension):
                references.setdefault(target, []).append(file.name + pointer)
            if isinstance(value, str) and len(YSP_CALL.findall(value)) > len(YSP_LITERAL.findall(value)):
                dynamic_ysp.append(file.name + pointer)
    system = json.loads((www / "data/System.json").read_text(encoding="utf-8-sig"))
    for target in system_audio(system, extension):
        references.setdefault(target, []).append("System.json")
    actual = {file.relative_to(www).as_posix() for category in ("movies", "audio")
              for file in (www / category).rglob("*") if file.is_file()}
    folded = {name.casefold(): name for name in actual}
    missing = {name: locations for name, locations in references.items() if name.casefold() not in folded}
    case = {name: folded[name.casefold()] for name in references
            if name not in actual and name.casefold() in folded}
    return {"unique_literal_paths": len(references), "missing": missing, "case_differences": case,
            "dynamic_ysp_calls_unresolved": dynamic_ysp,
            "scope": "All data/*.json standard video/audio commands, map autoplay, System audio and literal YSP calls; no reachability proof or arbitrary JS evaluation"}
