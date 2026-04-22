from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Optional


def make_default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_resolved.xlsx")


def parse_limit(value: str) -> Optional[int]:
    raw = value.strip()
    if not raw:
        return None
    limit = int(raw)
    if limit <= 0:
        raise ValueError("Limit must be a positive integer")
    return limit


def open_path(path: Path) -> None:
    target = str(path)
    system = platform.system().lower()
    if system.startswith("win"):
        os.startfile(target)  # type: ignore[attr-defined]
        return
    if system == "darwin":
        subprocess.run(["open", target], check=False)
        return
    subprocess.run(["xdg-open", target], check=False)
