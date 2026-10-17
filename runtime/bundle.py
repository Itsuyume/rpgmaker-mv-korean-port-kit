"""Build a new, unpacked app with a minimal MV runtime overlay."""

import json
from pathlib import Path
import plistlib
import shutil
import tempfile

from .archive import extract_runtime, validate_runtime_archive
from .config import RuntimeSpec
from .files import (FONT_DESTINATION, LICENSE_DESTINATION, OVERLAY_FILES, game_hashes,
                    patch_index, validate_game, validate_manifest, validate_package, write_json)
from .shared.archive import sha256_file
from .shared import native


def validate_output(www: Path, package: Path, output: Path, report: Path) -> None:
    if output.suffix != ".app" or output.exists() or report.exists():
        raise ValueError("App output must be a new .app path; report must also be new")
    for path in (output.resolve(), report.resolve()):
        if path.is_relative_to(www.resolve()) or path == package.resolve():
            raise ValueError("Output must not overlap a game input")
    if not output.parent.is_dir() or not report.parent.is_dir():
        raise ValueError("App and report parent directories must already exist")
    save = www / "save"
    if save.exists() and (not save.is_dir() or any(save.iterdir())):
        raise ValueError("www/save contains data; packaging personal saves is not allowed")


def configure_package(original: dict, spec: RuntimeSpec) -> dict:
    manifest = json.loads(json.dumps(original))
    manifest["name"] = spec.package_name
    manifest["window"]["title"] = spec.display_name
    manifest["pq-runtime"] = {"schema": 1, "profile": spec.package_name}
    if "product_string" in manifest:
        raise ValueError("Unexpected product_string; preserve official NW.js helper names")
    return manifest


def configure_bundle(app: Path, spec: RuntimeSpec) -> None:
    target = app / "Contents/Info.plist"
    info = plistlib.loads(target.read_bytes())
    info.update({"CFBundleIdentifier": spec.bundle_id, "CFBundleDisplayName": spec.display_name,
                 "CFBundleShortVersionString": "412.0", "CFBundleVersion": "412.1"})
    target.write_bytes(plistlib.dumps(info))


def validate_font(font: Path, license_file: Path, spec: RuntimeSpec) -> None:
    if font.name != spec.font_filename or sha256_file(font) != spec.font_sha256:
        raise ValueError("Font does not match the pinned Noto Sans CJK KR dependency")
    if sha256_file(license_file) != spec.font_license_sha256:
        raise ValueError("Font license does not match the retained OFL dependency")


def copy_payload(www: Path, app: Path, package: dict, spec: RuntimeSpec,
                 font: Path, license_file: Path) -> dict:
    payload = app / "Contents/Resources/app.nw"
    if payload.exists():
        raise ValueError("Vendor runtime unexpectedly contains an app.nw payload")
    payload.mkdir()
    target = payload / "www"
    native.copy_app(www, target)
    save = target / "save"
    excluded = []
    if save.exists():
        save.rmdir()
        excluded.append("save/")
    overlay = target / "mac"
    if overlay.exists():
        raise ValueError("Game already contains the reserved mac runtime directory")
    overlay.mkdir()
    for destination, source in OVERLAY_FILES.items():
        shutil.copyfile(Path(__file__).with_name(source), target / destination)
    (overlay / "fonts").mkdir()
    shutil.copyfile(font, target / FONT_DESTINATION)
    shutil.copyfile(license_file, target / LICENSE_DESTINATION)
    patch = patch_index(target / "index.html")
    write_json(payload / "package.json", configure_package(package, spec))
    return {"index_patch": patch, "excluded_empty_directories": excluded,
            "added_game_files": sorted([*OVERLAY_FILES, FONT_DESTINATION, LICENSE_DESTINATION])}


def verify_payload(app: Path, original: dict[str, str]) -> dict:
    target = app / "Contents/Resources/app.nw/www"
    after = game_hashes(target)
    missing = sorted(set(original) - set(after))
    added = sorted(set(after) - set(original))
    changed = sorted(name for name in original if name in after and original[name] != after[name])
    expected = sorted([*OVERLAY_FILES, FONT_DESTINATION, LICENSE_DESTINATION])
    if missing or added != expected or changed != ["index.html"]:
        raise ValueError(f"Unexpected payload delta: missing={missing}, added={added}, changed={changed}")
    return {"input_file_count": len(original), "byte_identical_input_files": len(original) - 1,
            "changed_input_files": changed, "added_game_files": added,
            "output_file_hashes": after}


def build_app(www: Path, package: Path, manifest: dict, archive: Path,
              output: Path, report: Path, spec: RuntimeSpec,
              font: Path, license_file: Path, *, prepare_only: bool = False) -> dict:
    validate_output(www, package, output, report)
    validate_game(www)
    package_data = validate_package(package)
    configure_package(package_data, spec)
    validate_font(font, license_file, spec)
    original = validate_manifest(www, package, manifest)
    archive_facts = validate_runtime_archive(archive, spec)
    # File-provider folders can synthesize FinderInfo on newly created app roots.
    # Assemble and sign on a physical local volume, then verify the copied result.
    with tempfile.TemporaryDirectory(prefix="pq-runtime-", dir="/private/tmp") as temporary:
        runtime_app = extract_runtime(archive, Path(temporary))
        shutil.copyfile(runtime_app.parent / "credits.html", runtime_app / "Contents/Resources/NWjs-credits.html")
        changes = copy_payload(www, runtime_app, package_data, spec, font, license_file)
        configure_bundle(runtime_app, spec)
        payload_facts = verify_payload(runtime_app, original)
        if not prepare_only:
            native.sign_app(runtime_app)
            native.verify_app(runtime_app)
        native.copy_app(runtime_app, output)
    if not prepare_only:
        native.verify_app(output)
    result = {"schema": 1, "game_version": spec.game_version, "runtime": archive_facts,
              "profile_name": spec.package_name, "changes": changes, "payload": payload_facts,
              "source_package_sha256": sha256_file(package), "gui_tested": False,
              "prepare_only": prepare_only, "signature_verified": not prepare_only,
              "input_file_hashes": original}
    write_json(report, result)
    return result
