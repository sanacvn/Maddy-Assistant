from __future__ import annotations

import os
from pathlib import Path


def _venv_python() -> Path | None:
    project_root = Path(__file__).resolve().parent.parent
    candidate = project_root / ".venv" / "bin" / "python"
    if candidate.exists():
        return candidate
    return None


def main() -> None:
    venv_python = _venv_python()
    if not venv_python:
        raise SystemExit(
            "Virtual environment tidak ditemukan. Jalankan `python3 -m venv .venv` lalu "
            "`./.venv/bin/pip install -r requirements.txt`."
        )

    project_root = Path(__file__).resolve().parent.parent
    os.execv(
        str(venv_python),
        [
            str(venv_python),
            "-m",
            "bot",
        ],
    )


if __name__ == "__main__":
    main()
