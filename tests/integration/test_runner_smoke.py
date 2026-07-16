import os
import subprocess
from pathlib import Path


def test_runner_handles_non_tty():
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [".venv/bin/python", "-m", "aegis_phase1.v2.runner"],
        input="",
        capture_output=True,
        text=True,
        timeout=30,
        cwd=repo_root,
        env=os.environ.copy(),
    )

    assert result.returncode == 0
    assert "Interactive wizard requires a TTY" in result.stdout
    assert "pre_selected" not in result.stderr
