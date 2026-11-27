"""Deterministic stand-in for the model, used when no ANTHROPIC_API_KEY is available.

It reads the agent's spec header out of the system prompt and answers from templates. Everything it
produces is generic scaffolding, not an app designed for the idea: stories are the same three
placeholders with the idea text pasted in, Kotlin files are stubs, and the generated tests fail on
purpose (`fail(...)`), so they can never be mistaken for passing acceptance tests. Runs that use it
prove the plumbing (schemas, verifiers, orchestrator, report) and nothing about model quality.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .paths import module_dir

IDEA = re.compile(r'<untrusted name="goal">\n(.*?)\n</untrusted>', re.S)
STORY = re.compile(r'<untrusted name="story">\n(.*?)\n</untrusted>', re.S)
LINES = re.compile(r'<untrusted name="acceptance-lines">\n(.*?)\n</untrusted>', re.S)
MODULE = re.compile(r"for module (\S+?)\.\n")
APP = re.compile(r"for module (\S+?)\. ")
CAMEL = re.compile(r"[^A-Za-z0-9]+")

MODULE_GRAPH = {"modules": [
    {"path": ":app", "layer": "app", "depends_on": [":feature:items", ":data", ":domain", ":core"]},
    {"path": ":feature:items", "layer": "ui", "depends_on": [":domain", ":core"]},
    {"path": ":domain", "layer": "domain", "depends_on": [":core"]},
    {"path": ":data", "layer": "data", "depends_on": [":domain", ":core"]},
    {"path": ":core", "layer": "core", "depends_on": []}],
    "adrs": ["Hilt for DI", "Room for local storage", "Single-activity Compose navigation"]}


def _pascal(s: str) -> str:
    return "".join(w.capitalize() for w in CAMEL.split(s) if w) or "Item"


@dataclass
class FakeModelClient:
    calls: list[str] = field(default_factory=list)   # agent header of each call

    def complete(self, system: str, user: str, max_tokens: int = 8192) -> str:
        head = system.lstrip().split("\n", 1)[0]
        self.calls.append(head)
        if head.startswith("# Product Strategist"):
            return json.dumps(self._prd(user))
        if head.startswith("# Android Architect"):
            return json.dumps(MODULE_GRAPH)
        if head.startswith("# UI Engineer"):
            return json.dumps(self._code(user, "ui"))
        if head.startswith("# Domain and Data Engineer"):
            return json.dumps(self._code(user, "data"))
        if head.startswith("# Test Engineer"):
            return json.dumps(self._tests(user))
        raise ValueError(f"FakeModelClient has no template for {head!r}")

    @staticmethod
    def _prd(user: str) -> dict:
        m = IDEA.search(user)
        idea = " ".join((m.group(1) if m else "an app").split())
        name = _pascal(" ".join(idea.split()[:2]))
        stories = [
            ("s1", "add an entry", "I can capture what matters", ["Given the app is open", "When I add an entry", "Then it appears in the list"]),
            ("s2", "see my entries after restarting", "nothing is lost", ["Given I added an entry", "When I restart the app", "Then the entry is still listed"]),
            ("s3", "remove an entry", "the list stays relevant", ["Given an entry exists", "When I remove it", "Then it is no longer listed"]),
        ]
        return {"id": f"prd-{name.lower()}", "app_name": name, "min_sdk": 26, "target_sdk": 36,
                "stories": [{"id": i, "as_a": "user", "i_want": w, "so_that": f"{s} ({idea})", "acceptance": a}
                            for i, w, s, a in stories],
                "mvp_cut": ["s1", "s2", "s3"], "budgets": {"cold_start_ms": 800, "apk_mb": 15}}

    @staticmethod
    def _code(user: str, kind: str) -> dict:
        module = MODULE.search(user).group(1)
        story = json.loads(STORY.search(user).group(1))
        sid = story["id"]
        root = module_dir(module)
        if kind == "ui":
            body = (f"package app.ui\n\n// FAKE MODEL STUB for story {sid}: not a real screen.\n"
                    f"fun screen{sid.upper()}(): String = \"stub\"\n")
            path = f"{root}/src/main/kotlin/Screen{sid.upper()}.kt"
        else:
            body = (f"package app.data\n\n// FAKE MODEL STUB for story {sid}: not a real repository.\n"
                    f"class Repo{sid.upper()} {{ fun items(): List<String> = emptyList() }}\n")
            path = f"{root}/src/main/kotlin/Repo{sid.upper()}.kt"
        return {"module": module, "summary": f"fake stub for {sid}", "files": [{"path": path, "content": body}]}

    @staticmethod
    def _tests(user: str) -> dict:
        lines = [l.split(":", 1) for l in LINES.search(user).group(1).splitlines() if ":" in l]
        app = re.search(r"for module (\S+?)\. ", user).group(1)
        root = module_dir(app)
        body = ["package app", "", "import org.junit.Assert.fail", "import org.junit.Test", "",
                "// FAKE MODEL PLACEHOLDERS: every test fails on purpose until a real test is written.",
                "class AcceptanceTest {"]
        for key, _text in lines:
            body += [f"    // ACCEPTANCE {key.strip()}", "    @Test",
                     f"    fun `acceptance {key.strip()}`() {{ fail(\"placeholder from fake model\") }}", ""]
        body.append("}")
        return {"module": app, "summary": "fake placeholder tests",
                "files": [{"path": f"{root}/src/test/kotlin/AcceptanceTest.kt", "content": "\n".join(body) + "\n"}]}
