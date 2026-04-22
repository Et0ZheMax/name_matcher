from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional


class CallbackHandler(logging.Handler):
    def __init__(self, callback: Callable[..., None]) -> None:
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)
        try:
            self.callback(record.levelname, message)
        except TypeError:
            self.callback(message)


def setup_logging(logs_dir: Path, debug: bool = False, callback: Optional[Callable[..., None]] = None) -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("org_name_enricher")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.addHandler(ch)

    fh = logging.FileHandler(logs_dir / "run.log", encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    if callback:
        cb = CallbackHandler(callback)
        cb.setFormatter(fmt)
        cb.setLevel(logging.INFO)
        logger.addHandler(cb)

    return logger
