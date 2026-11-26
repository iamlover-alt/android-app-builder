"""UI Engineer and Domain/Data Engineer: module graph + story -> Kotlin files (schemas/code-change.schema.json).

Both emit the same `code-change` artifact; they differ in which module layers they may write and
which imports are forbidden there. `run_code_agent` applies the files through the Day 2
edit-then-lint tool, so a lint failure rolls the workspace back and surfaces as a fix round.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ..tools import EditResult, EditThenLint
from .paths import SECRET_RE, module_dir, path_errors, symlink_errors
from .runner import AgentDef, AgentOutputError, AgentRunner, wrap_untrusted



def database_annotations(text: str) -> list[str]:
    """Argument text of each @Database(...) with balanced parentheses (nested AutoMigration(...) etc.)."""
    out = []
    for m in re.finditer(r"@Database\s*\(", text):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += (text[i] == "(") - (text[i] == ")")
            i += 1
        out.append(text[m.end(): i - 1] if depth == 0 else text[m.end():])
    return out


MIGRATION = re.compile(r"\b(?:Migration|AutoMigration)\s*\(")
VERSION = re.compile(r"\bversion\s*=\s*(\d+)")


def _build_user(what: str):
    def build(inputs: dict[str, Any]) -> str:
        return (f"{what} for module {inputs['module']}.\n"
                + wrap_untrusted("module-graph", json.dumps(inputs["module_graph"], indent=1)) + "\n"
                + wrap_untrusted("story", json.dumps(inputs["story"], indent=1)))
    return build


def _verifier(layers: set[str], forbidden_imports: tuple[str, ...], allow_schema_json: bool):
    def verify(doc: Any, inputs: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        mods = {m["path"]: m for m in inputs["module_graph"]["modules"]}
        mod = mods.get(inputs["module"])
        if mod is None:
            return [f"unknown target module {inputs['module']!r}"]
        if mod["layer"] not in layers:
            errs.append(f"module {mod['path']} has layer {mod['layer']}; this agent writes only {sorted(layers)}")
        if doc["module"] != inputs["module"]:
            errs.append(f"module must be {inputs['module']!r}, got {doc['module']!r}")
        root = module_dir(mod["path"]) + "/src/"
        seen: set[str] = set()
        old_version = inputs.get("db_version")
        for f in doc["files"]:
            p, text = f["path"], f["content"]
            e = path_errors(p)
            schema_root = root.replace("/src/", "/schemas/")
            is_schema = allow_schema_json and p.startswith(schema_root)
            if not e and not (p.startswith(root) or is_schema):
                e = [f"path {p!r} must be under {root}" + (f" or {schema_root}" if allow_schema_json else "")]
            if not e and not (p.endswith(".kt") or (is_schema and p.endswith(".json"))):
                e = [f"path {p!r}: only .kt files are allowed"]
            if p in seen:
                e = e + [f"duplicate path {p!r}"]
            seen.add(p)
            errs += e
            if SECRET_RE.search(text):
                errs.append(f"{p}: contains secret-looking text")
            if p.endswith(".kt"):
                errs += [f"{p}: forbidden import {m!r} in a {mod['layer']} module"
                         for m in forbidden_imports if re.search(rf"^\s*import\s+{re.escape(m)}", text, re.M)]
                all_text = "\n".join(x["content"] for x in doc["files"] if x["path"].endswith(".kt"))
                for ann in database_annotations(text):
                    if not re.search(r"exportSchema\s*=\s*true", ann) or re.search(r"exportSchema\s*=\s*false", ann):
                        errs.append(f"{p}: @Database must set exportSchema = true")
                    v = VERSION.search(ann)
                    if not v:
                        errs.append(f"{p}: @Database must state version = N")
                        continue
                    ver = int(v.group(1))
                    if doc.get("db_version") != ver:
                        errs.append(f"{p}: db_version must equal the @Database version ({ver})")
                    if ver > int(old_version or 1) and not MIGRATION.search(all_text):
                        errs.append(f"{p}: database version {ver} needs a Migration(...) or AutoMigration(...) in the change")
        return errs
    return verify


UI_RULES = ("Rules: Kotlin + Compose + Material 3 only. Files go under <module dir>/src/. Do not import "
            "androidx.room or data-layer code. Set `module` to the target module path.\n")
DATA_RULES = ("Rules: Kotlin only (Room schema exports under <module dir>/schemas/ allowed in a data module). "
              "No androidx.compose imports. @Database needs exportSchema = true; raising the version needs a "
              "Migration/AutoMigration and `db_version`. Set `module` to the target module path.\n")

UI_ENGINEER = AgentDef(
    "ui-engineer", "code-change", _build_user("Implement the Compose screens and navigation for this story"),
    _verifier({"ui", "app"}, ("androidx.room",), False), UI_RULES)
DATA_ENGINEER = AgentDef(
    "data-engineer", "code-change", _build_user("Implement the ViewModel, use cases, repository and storage for this story"),
    _verifier({"domain", "data"}, ("androidx.compose",), True), DATA_RULES)


def run_code_agent(runner: AgentRunner, agent: AgentDef, inputs: dict[str, Any], editor: EditThenLint,
                   feedback: list[str] | None = None) -> tuple[dict[str, Any], EditResult]:
    """Model call -> verify -> edit-then-lint. A lint rejection raises AgentOutputError (workspace is rolled back)."""
    doc = runner.run(agent, inputs, feedback)
    links = [m for f in doc["files"] for m in symlink_errors(editor.workspace, f["path"])]
    if links:
        raise AgentOutputError(links)
    res = editor.apply({f["path"]: f["content"] for f in doc["files"]})
    if not res.applied:
        raise AgentOutputError([f"lint: {m}" for m in res.lint.messages] or ["lint failed"])
    return doc, res
