from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from app.models import PipelineResult


@dataclass(slots=True)
class GuiRunConfig:
    input_path: Path
    output_path: Path
    mode: str
    org_column: Optional[str]
    first_column_as_org: bool
    limit: Optional[int]
    no_cache: bool
    resume: bool
    debug: bool


@dataclass(slots=True)
class LogEvent:
    kind: Literal["log"]
    level: str
    message: str


@dataclass(slots=True)
class ProgressEvent:
    kind: Literal["progress"]
    idx: int
    total: int
    organization: str


@dataclass(slots=True)
class SuccessEvent:
    kind: Literal["success"]
    result: PipelineResult
    output_path: Path


@dataclass(slots=True)
class ErrorEvent:
    kind: Literal["error"]
    message: str
    traceback_text: str
