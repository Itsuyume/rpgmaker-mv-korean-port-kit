"""Static JS syntax check in an explicit local Node executable; no execution."""
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


def check_syntax(content: bytes, executable: str) -> None:
    with TemporaryDirectory(prefix="localization-js-syntax-") as folder:
        source = Path(folder) / "candidate.js"
        source.write_bytes(content)
        result = subprocess.run([executable, "--check", str(source)], capture_output=True,
                                text=True, timeout=30, check=False)
        if result.returncode:
            raise ValueError("Generated JS failed static syntax check: " + result.stderr.strip())
