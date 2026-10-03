"""The frozen v0 copy used by the equivalence test must match the v0-university tag."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
V0_DIR = Path(__file__).parent / "v0_reference"
FILES = ["agents.py", "states.py", "utils.py", "simulate.py", "metrics.py"]


def _normalise(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")  # core.autocrlf may convert on checkout


@pytest.mark.parametrize("name", FILES)
def test_reference_file_matches_tag(name):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    proc = subprocess.run(["git", "show", f"v0-university:src/{name}"], cwd=REPO, capture_output=True, check=False)
    if proc.returncode != 0:
        pytest.skip(f"tag v0-university not available: {proc.stderr.decode(errors='replace')}")
    assert _normalise((V0_DIR / name).read_bytes()) == _normalise(proc.stdout)
