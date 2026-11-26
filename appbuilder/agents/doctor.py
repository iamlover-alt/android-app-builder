"""Build Doctor: Gradle errors -> smallest patch, failure memory first, at most 5 rounds.

Per round: build; if red, look the error signature up in failure memory. A stored fix is applied
without a model call; if the build is still red it is reverted and counted as a miss, and the model
is used on the next round. Model patches (schemas/build-fix.schema.json) are applied through the
Day 2 edit-then-lint tool. The patch that turns the build green is recorded under the signature of
the errors it was applied to. Multi-round fix chains are not recorded as chains (only the last step).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..tools import EditThenLint, GradleRunner
from .memory import FailureMemory, FixEntry, signature
from .paths import SECRET_RE, patch_path_errors, symlink_errors
from .runner import AgentDef, AgentOutputError, AgentRunner, wrap_untrusted

MAX_ROUNDS = 5
MAX_FILE_CHARS = 6000
MAX_CONTEXT_FILES = 4
ERR_PATH = re.compile(r"(?:file://)?((?:/|[\w.\-]+/)[\w.\-/@+]*\.(?:kt|kts|java|xml|pro|toml|properties))")


class PatchError(ValueError):
    pass


def apply_patches(project: Path, patches: list[dict[str, str]], editor: EditThenLint | None = None) -> dict[str, str]:
    """Compute new file contents; each `find` must occur exactly once. Returns {path: new_content}."""
    out: dict[str, str] = {}
    for p in patches:
        errs = patch_path_errors(p["path"]) or symlink_errors(project, p["path"])
        if errs:
            raise PatchError(errs[0])
        f = Path(project) / p["path"]
        text = out.get(p["path"])
        if text is None:
            if not f.is_file():
                raise PatchError(f"{p['path']}: file does not exist")
            text = f.read_text(encoding="utf-8")
        n = text.count(p["find"])
        if n != 1:
            raise PatchError(f"{p['path']}: `find` text occurs {n} times (need exactly 1)")
        out[p["path"]] = text.replace(p["find"], p["replace"], 1)
    return out


def context_files(project: Path, errors: list[str]) -> dict[str, str]:
    """Source files mentioned in error lines, inside the project, truncated."""
    root = Path(project).resolve()
    found: dict[str, str] = {}
    for e in errors:
        for m in ERR_PATH.findall(e):
            p = (Path(m) if m.startswith("/") else root / m).resolve()
            if root in p.parents and p.is_file():
                rel = str(p.relative_to(root))
                if not patch_path_errors(rel) and not symlink_errors(root, rel) and len(found) < MAX_CONTEXT_FILES:
                    with p.open(encoding="utf-8", errors="replace") as fh:
                        text = fh.read(MAX_FILE_CHARS)
                    if not SECRET_RE.search(text):  # never send secret-looking files to the model
                        found.setdefault(rel, text)
    return found


def _build_user(inputs: dict[str, Any]) -> str:
    parts = ["Fix this Gradle build failure with the smallest patch.",
             wrap_untrusted("errors", "\n".join(inputs["errors"]))]
    for rel, text in inputs.get("files", {}).items():
        parts.append(wrap_untrusted("file-" + re.sub(r"[^A-Za-z0-9_-]", "_", rel), f"// {rel}\n{text}"))
    return "\n".join(parts)


def _verify(doc: Any, inputs: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    for p in doc["patches"]:
        errs += patch_path_errors(p["path"])
        if SECRET_RE.search(p["find"] + p["replace"]):
            errs.append(f"{p['path']}: patch contains secret-looking text")
        if p["find"] == p["replace"]:
            errs.append(f"{p['path']}: patch changes nothing")
    return errs


BUILD_DOCTOR = AgentDef(
    "build-doctor", "build-fix", _build_user, _verify,
    "Rules: smallest patch only. Each `find` must be copied exactly from the provided file and occur once. "
    "Do not touch signing files, local.properties or the Gradle wrapper.\n")


@dataclass
class DoctorReport:
    green: bool
    rounds: int
    escalated: bool = False
    steps: list[dict[str, Any]] = field(default_factory=list)   # {round, source, signature, outcome}
    last_errors: tuple[str, ...] = ()
    dirty: bool = False      # a revert failed: tree holds an unwanted patch
    patched: bool = False    # partial progress patches were left in the tree (not green)

    @property
    def model_calls(self) -> int:
        return sum(s["source"] == "model" for s in self.steps)


class BuildDoctor:
    def __init__(self, runner: AgentRunner, memory: FailureMemory, gradle: GradleRunner,
                 editor: EditThenLint, project: Path, task: str = "assembleDebug",
                 max_rounds: int = MAX_ROUNDS) -> None:
        self.runner, self.memory, self.gradle, self.editor = runner, memory, gradle, editor
        self.project, self.task = Path(project), task
        self.max_rounds = min(max_rounds, MAX_ROUNDS)

    def _apply(self, patches: list[dict[str, str]]) -> tuple[dict[str, str | None], str | None]:
        """Apply patches via edit-then-lint. Returns (undo edits, error)."""
        try:
            new = apply_patches(self.project, patches)
        except PatchError as e:
            return {}, str(e)
        undo: dict[str, str | None] = {p: (self.project / p).read_text(encoding="utf-8") for p in new}
        res = self.editor.apply(new)
        if not res.applied:
            return {}, "lint rejected patch: " + "; ".join(res.lint.messages)[:300]
        return undo, None

    def fix(self) -> DoctorReport:
        rep = DoctorReport(False, 0)
        tried_memory: set[str] = set()
        feedback: list[str] = []
        result = self.gradle.run(self.project, self.task)
        while not result.ok and rep.rounds < self.max_rounds:
            errors = list(result.errors) or [result.log_tail[-300:] or "build failed"]
            sig = signature(errors)
            rep.rounds += 1
            entry: FixEntry | None = None if sig in tried_memory else self.memory.lookup(errors)
            step = {"round": rep.rounds, "signature": sig}
            if entry:
                tried_memory.add(sig)
                undo, err = self._apply(entry.patches)
                if err:
                    self.memory.mark(sig, False)
                    rep.steps.append({**step, "source": "memory", "outcome": f"not applicable: {err}"})
                    continue
                after = self.gradle.run(self.project, self.task)
                if after.ok:
                    self.memory.mark(sig, True)
                    rep.steps.append({**step, "source": "memory", "outcome": "green"})
                    result = after
                    break
                self.memory.mark(sig, False)
                if not self.editor.apply(undo).applied:  # revert so the model starts from the failing state
                    rep.steps.append({**step, "source": "memory", "outcome": "revert failed: tree is dirty"})
                    rep.dirty = True
                    break
                rep.steps.append({**step, "source": "memory", "outcome": "reverted: build still red"})
                continue
            inputs = {"errors": errors, "files": context_files(self.project, errors)}
            try:
                doc = self.runner.run(BUILD_DOCTOR, inputs, feedback or None)
            except AgentOutputError as e:
                feedback = e.errors
                rep.steps.append({**step, "source": "model", "outcome": "invalid reply"})
                continue
            undo, err = self._apply(doc["patches"])
            if err:
                feedback = [err]
                rep.steps.append({**step, "source": "model", "outcome": f"patch failed: {err}"})
                continue
            feedback = []
            after = self.gradle.run(self.project, self.task)
            if after.ok:
                self.memory.record(errors, doc["diagnosis"], doc["patches"])
                rep.steps.append({**step, "source": "model", "outcome": "green"})
                result = after
                break
            if signature(list(after.errors) or ["build failed"]) == sig:  # no progress: undo the patch
                if not self.editor.apply(undo).applied:
                    rep.dirty = True
                    rep.steps.append({**step, "source": "model", "outcome": "no progress; revert failed: tree is dirty"})
                    break
                feedback = ["your previous patch was applied but the build errors did not change; it was reverted"]
                rep.steps.append({**step, "source": "model", "outcome": "no progress; reverted"})
            else:
                rep.steps.append({**step, "source": "model", "outcome": "patched; errors changed, kept"})
                rep.patched = True
            result = after
        rep.green = result.ok
        rep.last_errors = tuple(result.errors)
        rep.escalated = not rep.green
        return rep
