"""The fixed macOS copy, signature and archive commands."""

from pathlib import Path
import subprocess


def run(arguments: list[str]) -> None:
    result = subprocess.run(arguments, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{Path(arguments[0]).name} exited {result.returncode}: {detail}")


def copy_app(source: Path, destination: Path) -> None:
    run(["/usr/bin/ditto", "--noextattr", "--norsrc", "--noqtn",
         str(source), str(destination)])


def sign_app(app: Path) -> None:
    run(["/usr/bin/xattr", "-cr", str(app)])
    run(["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(app)])


def verify_app(app: Path) -> None:
    run(["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)])


def create_zip(folder: Path, archive: Path) -> None:
    run(["/usr/bin/ditto", "-c", "-k", "--keepParent", "--noextattr", "--norsrc",
         "--noqtn", str(folder), str(archive)])


def extract_zip(archive: Path, destination: Path) -> None:
    run(["/usr/bin/ditto", "-x", "-k", "--noextattr", "--norsrc", "--noqtn",
         str(archive), str(destination)])
