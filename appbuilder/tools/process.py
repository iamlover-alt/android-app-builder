"""Subprocess abstraction. argv lists only (never a shell), scrubbed env, hard timeout."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol, Sequence

# Only these variables are passed to children. Secrets (ANTHROPIC_API_KEY, signing
# keys, Play credentials) are therefore never visible to Gradle, adb or linters.
ENV_ALLOWLIST = ("PATH", "HOME", "JAVA_HOME", "ANDROID_HOME", "ANDROID_SDK_ROOT",
                 "GRADLE_USER_HOME", "LANG", "TMPDIR")
MAX_OUTPUT = 200_000


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


class CommandRunner(Protocol):
    def run(self, argv: Sequence[str], cwd: Path, timeout: float) -> CommandResult: ...


class SubprocessRunner:
    def run(self, argv: Sequence[str], cwd: Path, timeout: float = 600) -> CommandResult:
        if isinstance(argv, str):
            raise TypeError("argv must be a sequence, not a string (no shell)")
        env = {k: v for k, v in os.environ.items() if k in ENV_ALLOWLIST}
        try:
            p = subprocess.run(list(argv), cwd=cwd, env=env, capture_output=True,
                               text=True, timeout=timeout, shell=False)
        except subprocess.TimeoutExpired as e:
            out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            return CommandResult(tuple(argv), -1, out[-MAX_OUTPUT:], "timeout", True)
        except FileNotFoundError as e:
            return CommandResult(tuple(argv), 127, "", str(e))
        return CommandResult(tuple(argv), p.returncode, p.stdout[-MAX_OUTPUT:], p.stderr[-MAX_OUTPUT:])


@dataclass
class FakeRunner:
    """Scripted runner: handler(argv) -> CommandResult, or a fixed default. Records calls."""
    handler: Callable[[Sequence[str]], CommandResult] | None = None
    default: CommandResult | None = None
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def run(self, argv: Sequence[str], cwd: Path, timeout: float = 600) -> CommandResult:
        self.calls.append(tuple(argv))
        if self.handler:
            return self.handler(argv)
        return self.default or CommandResult(tuple(argv), 0)
