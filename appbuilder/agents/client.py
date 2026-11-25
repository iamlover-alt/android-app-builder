"""Model clients. The runner only sees the ModelClient interface.

- AnthropicClient: Messages API over HTTPS (stdlib only). Key comes from the
  ANTHROPIC_API_KEY environment variable and is held in memory only: it is never
  written to files, logs, error messages or prompts.
- RecordedClient: replays canned responses (tests, offline runs) and records
  the requests it received so tests can assert on prompts.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5-5"
KEY_ENV = "ANTHROPIC_API_KEY"


class ModelError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # never forward the key to another location
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class ModelClient(Protocol):
    def complete(self, system: str, user: str, max_tokens: int = 8192) -> str: ...


class AnthropicClient:
    def __init__(self, model: str | None = None, timeout: float = 120.0,
                 environ: dict[str, str] | None = None, url: str = API_URL) -> None:
        env = os.environ if environ is None else environ
        self._key = env.get(KEY_ENV, "")
        if not self._key:
            raise ModelError(f"{KEY_ENV} is not set in the environment")
        self.model = model or env.get("APPBUILDER_MODEL") or DEFAULT_MODEL
        self.timeout = timeout
        u = urllib.parse.urlparse(url)
        if u.scheme != "https" and not (u.scheme == "http" and u.hostname in LOOPBACK):
            raise ModelError("API url must be https (http only for loopback test servers)")
        self.url = url

    def __repr__(self) -> str:  # never expose the key
        return f"AnthropicClient(model={self.model!r})"

    def complete(self, system: str, user: str, max_tokens: int = 8192) -> str:
        body = json.dumps({
            "model": self.model, "max_tokens": max_tokens, "system": system,
            "messages": [{"role": "user", "content": user}],
        }).encode()
        req = urllib.request.Request(self.url, data=body, method="POST", headers={
            "content-type": "application/json", "x-api-key": self._key,
            "anthropic-version": API_VERSION})
        try:
            with _OPENER.open(req, timeout=self.timeout) as resp:  # noqa: S310 (fixed https URL)
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise ModelError(f"Anthropic API returned HTTP {e.code}") from None  # body/headers omitted on purpose
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            raise ModelError(f"Anthropic API call failed: {type(e).__name__}") from None
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        if not text:
            raise ModelError("Anthropic API returned no text content")
        return text


@dataclass
class Call:
    system: str
    user: str


@dataclass
class RecordedClient:
    """Replays `responses` in order (last one repeats if `repeat_last`)."""
    responses: list[str]
    repeat_last: bool = False
    calls: list[Call] = field(default_factory=list)

    def complete(self, system: str, user: str, max_tokens: int = 8192) -> str:
        self.calls.append(Call(system, user))
        i = len(self.calls) - 1
        if i >= len(self.responses):
            if self.repeat_last and self.responses:
                return self.responses[-1]
            raise ModelError("RecordedClient has no more recorded responses")
        return self.responses[i]
