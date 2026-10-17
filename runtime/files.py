"""Game input hashing and the explicit, additive boot hook."""

import hashlib
import json
import os
from pathlib import Path

from .shared.archive import sha256_file


MAIN_TAG = '<script type="text/javascript" src="js/main.js"></script>'
ADDIN_TAG = '<script type="text/javascript" src="mac/NativeRuntime.js"></script>'
FONT_TAG = '<script type="text/javascript" src="mac/KoreanFont.js"></script>'
CSS_TAG = '<link rel="stylesheet" type="text/css" href="mac/KoreanFont.css">'
OVERLAY_FILES = {"mac/NativeRuntime.js": "addin.js", "mac/KoreanFont.js": "font-fallback.js",
                 "mac/KoreanFont.css": "korean-font.css"}
FONT_DESTINATION = "mac/fonts/NotoSansCJKkr-Regular.otf"
LICENSE_DESTINATION = "mac/fonts/OFL.txt"
REQUIRED_GAME_FILES = ("index.html", "js/main.js", "js/rpg_core.js", "js/rpg_managers.js",
                       "js/plugins.js", "js/libs/lz-string.js", "data/System.json")


def walk_error(error: OSError) -> None:
    raise error


def game_hashes(root: Path) -> dict[str, str]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Game www input must be a real directory")
    result: dict[str, str] = {}
    for directory, directories, filenames in os.walk(root, followlinks=False, onerror=walk_error):
        for name in directories + filenames:
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError(f"Game input contains a symlink: {path.relative_to(root)}")
        for name in filenames:
            path = Path(directory) / name
            if not path.is_file():
                raise ValueError(f"Game input is not a regular file: {path.relative_to(root)}")
            result[path.relative_to(root).as_posix()] = sha256_file(path)
    return result


def source_manifest(www: Path, package: Path) -> dict:
    hashes = game_hashes(www)
    return {"schema": 1, "root_package_sha256": sha256_file(package), "www_files": hashes,
            "file_count": len(hashes), "bytes": sum((www / name).stat().st_size for name in hashes)}


def validate_game(www: Path) -> None:
    for name in REQUIRED_GAME_FILES:
        if not (www / name).is_file():
            raise ValueError(f"Required MV game file is missing: {name}")
    index = (www / "index.html").read_text(encoding="utf-8-sig")
    if index.count(MAIN_TAG) != 1 or ADDIN_TAG in index:
        raise ValueError("Expected one original MV main.js boot script")


def validate_manifest(www: Path, package: Path, manifest: dict) -> dict[str, str]:
    current = game_hashes(www)
    if manifest.get("schema") != 1 or current != manifest.get("www_files"):
        raise ValueError("www input does not match the supplied file manifest")
    if sha256_file(package) != manifest.get("root_package_sha256"):
        raise ValueError("Root package input does not match the supplied file manifest")
    return current


def patch_index(path: Path) -> dict[str, str]:
    before = path.read_bytes()
    marker = MAIN_TAG.encode("ascii")
    if before.count(marker) != 1 or ADDIN_TAG.encode("ascii") in before or before.count(b"</head>") != 1:
        raise ValueError("Expected exactly one unmodified MV main.js script tag")
    newline = b"\r\n" if b"\r\n" in before else b"\n"
    scripts = newline.join(b"        " + tag.encode("ascii") for tag in (FONT_TAG, ADDIN_TAG))
    after = before.replace(marker, marker + newline + scripts)
    after = after.replace(b"</head>", CSS_TAG.encode("ascii") + newline + b"    </head>")
    path.write_bytes(after)
    return {"before_sha256": hashlib.sha256(before).hexdigest(),
            "after_sha256": hashlib.sha256(after).hexdigest()}


def validate_package(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or data.get("main") != "www/index.html":
        raise ValueError("Expected the supplied root MV package with main=www/index.html")
    if not isinstance(data.get("window"), dict):
        raise ValueError("Root package window must be an object")
    if "node-main" in data or "inject_js_start" in data or "inject_js_end" in data:
        raise ValueError("Unexpected pre-existing NW.js startup hooks")
    return data


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
