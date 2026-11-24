"""gradle-run: run a whitelisted Gradle task via the project wrapper and summarise errors."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Sequence

from .process import CommandRunner

TASK_RE = re.compile(r"^:?[A-Za-z0-9_:-]+$")
ALLOWED_TASKS = {"assembleDebug", "assembleRelease", "bundleRelease", "testDebugUnitTest",
                 "lintDebug", "connectedDebugAndroidTest", "clean", "build"}
ERROR_RE = re.compile(r"^(e: .+|.*error:.+|FAILURE: .+|> Task .+ FAILED)$", re.M)


@dataclass(frozen=True)
class GradleResult:
    ok: bool
    task: str
    errors: tuple[str, ...] = ()
    log_tail: str = ""
    timed_out: bool = False


class GradleRunner(Protocol):
    def run(self, project: Path, task: str) -> GradleResult: ...


class GradleTool:
    def __init__(self, runner: CommandRunner, timeout: float = 1800, extra_args: Sequence[str] = ("--console=plain", "--offline")):
        self.runner, self.timeout, self.extra_args = runner, timeout, tuple(extra_args)

    def run(self, project: Path, task: str) -> GradleResult:
        name = task.split(":")[-1]
        if not TASK_RE.match(task) or name not in ALLOWED_TASKS:
            raise ValueError(f"gradle task not allowed: {task!r}")
        r = self.runner.run(["./gradlew", task, *self.extra_args], Path(project), self.timeout)
        text = r.stdout + "\n" + r.stderr
        return GradleResult(r.ok, task, tuple(dict.fromkeys(ERROR_RE.findall(text)))[:50],
                            text[-4000:], r.timed_out)


@dataclass
class FakeGradle:
    """results: task -> GradleResult (or error strings). Unknown tasks succeed."""
    failures: dict[str, tuple[str, ...]] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def run(self, project: Path, task: str) -> GradleResult:
        self.calls.append(task)
        errs = self.failures.get(task)
        return GradleResult(errs is None, task, errs or ())
