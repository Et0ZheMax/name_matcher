from urllib.error import URLError

from app.config import AppConfig
from app.sources.http_client import HttpClient


def test_get_text_retries_on_timeout(monkeypatch) -> None:
    cfg = AppConfig(max_retries=2, retry_backoff_sec=0)
    client = HttpClient(cfg)
    calls = {"count": 0}

    def _raise_timeout(*_args, **_kwargs):
        calls["count"] += 1
        raise TimeoutError("timed out")

    monkeypatch.setattr("app.sources.http_client.urlopen", _raise_timeout)

    assert client.get_text("https://example.org") is None
    assert calls["count"] == 2


def test_get_text_retries_on_url_error(monkeypatch) -> None:
    cfg = AppConfig(max_retries=3, retry_backoff_sec=0)
    client = HttpClient(cfg)
    calls = {"count": 0}

    def _raise_url_error(*_args, **_kwargs):
        calls["count"] += 1
        raise URLError("network")

    monkeypatch.setattr("app.sources.http_client.urlopen", _raise_url_error)

    assert client.get_text("https://example.org") is None
    assert calls["count"] == 3
