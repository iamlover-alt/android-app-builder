"""Edit-then-lint: apply file edits inside a workspace, lint, roll back everything on failure."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence

from .process import CommandRunner


class WorkspaceError(ValueError):
    """Edit path escapes the workspace."""


@dataclass(frozen=True)
class LintResult:
    ok: bool
    messages: tuple[str, ...] = ()


class Linter(Protocol):
    def lint(self, workspace: Path, changed: Sequence[Path]) -> LintResult: ...


@dataclass(frozen=True)
class EditResult:
    applied: bool          # True only if edits are kept (lint passed)
    rolled_back: bool
    lint: LintResult
    changed: tuple[str, ...] = ()


class EditThenLint:
    def __init__(self, workspace: Path, linter: Linter):
        self.workspace = Path(workspace).resolve()
        self.linter = linter

    def _resolve(self, rel: str) -> Path:
        p = (self.workspace / rel).resolve()
        if p != self.workspace and self.workspace not in p.parents:
            raise WorkspaceError(f"path escapes workspace: {rel}")
        if p == self.workspace or p.is_dir():
            raise WorkspaceError(f"not a file path: {rel}")
        return p

    def apply(self, edits: Mapping[str, str | None]) -> EditResult:
        """edits: relative path -> new full content, or None to delete the file."""
        targets = {rel: self._resolve(rel) for rel in edits}  # validate all before touching disk
        snapshot: dict[Path, bytes | None] = {
            p: (p.read_bytes() if p.exists() else None) for p in targets.values()}
        try:
            for rel, p in targets.items():
                content = edits[rel]
                if content is None:
                    p.unlink(missing_ok=True)
                else:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(content, encoding="utf-8")
            result = self.linter.lint(self.workspace, [p for p, c in zip(targets.values(), edits.values()) if c is not None])
        except BaseException:
            self._restore(snapshot)
            raise
        if result.ok:
            return EditResult(True, False, result, tuple(targets))
        self._restore(snapshot)
        return EditResult(False, True, result, tuple(targets))

    @staticmethod
    def _restore(snapshot: dict[Path, bytes | None]) -> None:
        for p, data in snapshot.items():
            if data is None:
                p.unlink(missing_ok=True)
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)


class CommandLinter:
    """Runs an external linter (e.g. ktlint) over changed files; non-zero exit = failure."""
    def __init__(self, runner: CommandRunner, base_argv: Sequence[str] = ("ktlint",), timeout: float = 120):
        self.runner, self.base_argv, self.timeout = runner, tuple(base_argv), timeout

    def lint(self, workspace: Path, changed: Sequence[Path]) -> LintResult:
        if not changed:
            return LintResult(True)
        argv = [*self.base_argv, *(str(p.relative_to(workspace)) for p in changed)]
        r = self.runner.run(argv, workspace, self.timeout)
        if r.ok:
            return LintResult(True)
        return LintResult(False, tuple((r.stdout + r.stderr).splitlines()[-50:]))


@dataclass
class FakeLinter:
    """Fails when check(path, text) returns a message. Default: pass."""
    check: Callable[[Path, str], str | None] = lambda p, t: None
    calls: int = 0

    def lint(self, workspace: Path, changed: Sequence[Path]) -> LintResult:
        self.calls += 1
        msgs = tuple(m for p in changed if (m := self.check(p, p.read_text(encoding="utf-8"))))
        return LintResult(not msgs, msgs)
