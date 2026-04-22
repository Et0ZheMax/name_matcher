from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional


class JsonCache:
    def __init__(self, cache_dir: Path, ttl_hours: int = 24, enabled: bool = True) -> None:
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_hours * 3600
        self.enabled = enabled
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, namespace: str, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        ns_dir = self.cache_dir / namespace
        ns_dir.mkdir(parents=True, exist_ok=True)
        return ns_dir / f"{digest}.json"

    def get(self, namespace: str, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        path = self._path(namespace, key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - payload["ts"] > self.ttl_seconds:
                return None
            return payload["value"]
        except Exception:
            return None

    def set(self, namespace: str, key: str, value: Any) -> None:
        if not self.enabled:
            return
        path = self._path(namespace, key)
        payload = {"ts": time.time(), "value": value}
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
