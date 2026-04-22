from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import AppConfig


class HttpClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        text = self.get_text(url, params=params)
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def get_text(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[str]:
        full = url
        if params:
            full = f"{url}?{urlencode(params)}"
        headers = {"User-Agent": self.config.user_agent}
        for attempt in range(1, self.config.max_retries + 1):
            req = Request(full, headers=headers)
            try:
                with urlopen(req, timeout=self.config.request_timeout_sec) as resp:
                    return resp.read().decode("utf-8", errors="ignore")
            except HTTPError as exc:
                if exc.code in {403, 404}:
                    return None
                if exc.code in {429, 500, 502, 503, 504}:
                    time.sleep(self.config.retry_backoff_sec * attempt)
                    continue
                return None
            except URLError:
                time.sleep(self.config.retry_backoff_sec * attempt)
                continue
        return None
