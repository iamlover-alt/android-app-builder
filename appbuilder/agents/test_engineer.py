"""Test Engineer: PRD acceptance lines -> test files, then an honest test-report.

Every Gherkin acceptance line of an MVP story is a criterion with a key like `s1#2` (story id,
1-based line number). The agent writes tests into the :app module (`src/test` for JVM tests,
`src/androidTest` for Compose UI tests) and marks which lines each test covers with comment
markers directly above `@Test`:

    // ACCEPTANCE s1#1
    // ACCEPTANCE s1#2
    @Test fun `adds a task`() { ... }

The report is built only from evidence: a criterion passes iff at least one test claims it, every
claiming test has a fresh JUnit XML result, and all of those passed. (A test with an empty body still
passes: the report proves the tests ran green, not that they assert anything meaningful.) No result file (tests not run, fake
Gradle, androidTest without an emulator) means `passed: false` with the reason as evidence.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree

from ..orchestrator import SchemaRegistry
from ..orchestrator.runlog import clip
from ..tools import EditThenLint, GradleRunner
from .paths import SECRET_RE, module_dir, path_errors, symlink_errors
from .runner import AgentDef, AgentOutputError, AgentRunner, wrap_untrusted

MARKER = re.compile(r"^[ \t]*//[ \t]*ACCEPTANCE[ \t]+(\S+)[ \t]*$", re.M)
TEST_BLOCK = re.compile(
    r"(?P<markers>(?:^[ \t]*//[ \t]*ACCEPTANCE[ \t]+\S+[ \t]*\n)+)"
    r"(?:[ \t]*//[^\n]*\n|[ \t]*\n)*"
    r"[ \t]*@Test\b(?:\([^)\n]*\))?\s*(?:@\w+(?:\([^)\n]*\))?\s*)*"
    r"(?:\w+[ \t]+)*fun[ \t]+(?P<name>`[^`\n]+`|\w+)", re.M)
CLASS_DECL = re.compile(r"^[ \t]*(?:\w+[ \t]+)*class[ \t]+(\w+)", re.M)
MAX_XML_BYTES = 2_000_000


@dataclass(frozen=True)
class Criterion:
    story_id: str
    index: int       # 1-based position in the story's acceptance list
    line: str

    @property
    def key(self) -> str:
        return f"{self.story_id}#{self.index}"


@dataclass(frozen=True)
class TestRef:
    __test__ = False  # not a pytest class
    key: str
    path: str
    source_set: str   # "test" (JVM) or "androidTest" (needs an emulator)
    cls: str
    name: str
    pkg: str = ""

    @property
    def full_class(self) -> str:
        return f"{self.pkg}.{self.cls}" if self.pkg else self.cls


def criteria(prd: dict[str, Any], story_ids: list[str] | None = None) -> list[Criterion]:
    """Acceptance lines of the MVP stories (or `story_ids`), in PRD order."""
    want = story_ids if story_ids is not None else prd.get("mvp_cut", [])
    return [Criterion(s["id"], i, line) for s in prd["stories"] if s["id"] in want
            for i, line in enumerate(s["acceptance"], 1)]


def app_module(module_graph: dict[str, Any]) -> str | None:
    return next((m["path"] for m in module_graph["modules"] if m["layer"] == "app"), None)


def acceptance_test_dirs(module_graph: dict[str, Any]) -> tuple[str, str]:
    root = module_dir(app_module(module_graph) or ":app")
    return f"{root}/src/test/", f"{root}/src/androidTest/"


def parse_tests(files: list[dict[str, str]]) -> tuple[list[TestRef], list[str]]:
    """Find marked @Test functions. Returns (refs, errors); one ref per (marker, test)."""
    refs: list[TestRef] = []
    errs: list[str] = []
    for f in files:
        p, text = f["path"], f["content"]
        if not p.endswith(".kt"):
            continue
        pkg = re.search(r"^\s*package\s+([\w.]+)", text, re.M)
        classes = [(c.start(), c.group(1)) for c in CLASS_DECL.finditer(text)]
        sset = "androidTest" if "/src/androidTest/" in p else "test"
        claimed = 0
        for m in TEST_BLOCK.finditer(text):
            keys = MARKER.findall(m.group("markers"))
            claimed += len(keys)
            owner = [n for pos, n in classes if pos < m.start()]
            if not (pkg and owner):
                errs.append(f"{p}: test files need a `package` line and a `class` declared above each test")
                break
            name = m.group("name").strip("`")
            refs += [TestRef(k, p, sset, owner[-1], name, pkg.group(1)) for k in keys]
        if claimed != len(MARKER.findall(text)):
            errs.append(f"{p}: every `// ACCEPTANCE <story>#<n>` marker must sit directly above an @Test function")
    return refs, errs


# ---- agent ---------------------------------------------------------------
def _build_user(inputs: dict[str, Any]) -> str:
    cs = criteria(inputs["prd"], inputs.get("story_ids"))
    lines = "\n".join(f"{c.key}: {c.line}" for c in cs)
    tdir, adir = acceptance_test_dirs(inputs["module_graph"])
    return (f"Write one test per acceptance line for module {app_module(inputs['module_graph'])}. "
            f"JVM/unit tests go under {tdir}, Compose UI tests under {adir}. The screens may not exist yet.\n"
            + wrap_untrusted("acceptance-lines", lines) + "\n"
            + wrap_untrusted("module-graph", json.dumps(inputs["module_graph"], indent=1)))


def _verify(doc: Any, inputs: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    app = app_module(inputs["module_graph"])
    if app is None:
        return ["module graph has no app module"]
    if doc["module"] != app:
        errs.append(f"module must be {app!r}, got {doc['module']!r}")
    tdir, adir = acceptance_test_dirs(inputs["module_graph"])
    seen: set[str] = set()
    for f in doc["files"]:
        p = f["path"]
        e = path_errors(p)
        if not e and not (p.startswith(tdir) or p.startswith(adir)):
            e = [f"path {p!r} must be under {tdir} or {adir}"]
        if not e and not p.endswith(".kt"):
            e = [f"path {p!r}: only .kt files are allowed"]
        if p in seen:
            e.append(f"duplicate path {p!r}")
        seen.add(p)
        errs += e
        if SECRET_RE.search(f["content"]):
            errs.append(f"{p}: contains secret-looking text")
    refs, perrs = parse_tests(doc["files"])
    errs += perrs
    want = {c.key for c in criteria(inputs["prd"], inputs.get("story_ids"))}
    got = {r.key for r in refs}
    errs += [f"acceptance line {k} has no test (add `// ACCEPTANCE {k}` above an @Test)" for k in sorted(want - got)]
    errs += [f"marker {k!r} does not match any acceptance line" for k in sorted(got - want)]
    return errs


TEST_ENGINEER = AgentDef(
    "test-engineer", "code-change", _build_user, _verify,
    "Rules: Kotlin, JUnit4 (and Compose test rules for UI). One test per acceptance line, or one test for "
    "several lines with one marker line each. Every `@Test` is preceded by `// ACCEPTANCE <story id>#<line "
    "number>` markers (line numbers start at 1 within the story). Files need `package` and `class`. Set `module` "
    "to the app module path. Never weaken or skip an assertion to make a test pass.\n")


# ---- results and report --------------------------------------------------
def parse_junit_dir(directory: Path) -> dict[tuple[str, str], tuple[str, str]]:
    """(full class name, test name) -> (status, detail) from JUnit XML files. Missing dir => {}.

    Untrusted input (test code can write these files): only plain ASCII-compatible XML without a DTD is
    read; anything else is skipped. On a duplicate key a failure beats a pass."""
    out: dict[tuple[str, str], tuple[str, str]] = {}
    d = Path(directory)
    if d.is_symlink() or not d.is_dir():
        return out
    for x in sorted(d.glob("*.xml")):
        try:
            if x.is_symlink() or not x.is_file() or x.stat().st_size > MAX_XML_BYTES:
                continue
            raw = x.read_bytes()
            if b"\x00" in raw or re.search(rb"<!(DOCTYPE|ENTITY)", raw, re.I) or not re.match(rb"\s*<", raw):
                continue  # NUL => UTF-16/32, which would hide a DTD from the check above
            root = ElementTree.fromstring(raw)
        except (OSError, ValueError, LookupError, ElementTree.ParseError):
            continue
        for tc in root.iter("testcase"):
            bad = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
            if bad is not None:
                res = ("failed", bad.get("message") or (bad.text or "").strip())
            elif tc.find("skipped") is not None:
                res = ("skipped", "")
            else:
                res = ("passed", "")
            key = (tc.get("classname") or "", tc.get("name") or "")
            if key not in out or (res[0] == "failed" and out[key][0] != "failed"):
                out[key] = res
    return out


def _ev(text: str) -> str:
    return clip(SECRET_RE.sub("[redacted]", text))


def build_report(task_id: str, prd: dict[str, Any], tests: list[TestRef], results: dict[tuple[str, str], tuple[str, str]],
                 build_green: bool, fix_rounds: int = 0, story_ids: list[str] | None = None,
                 unit_note: str = "") -> dict[str, Any]:
    """test-report document. `results` comes from real test execution; empty means nothing ran."""
    by_key: dict[str, list[TestRef]] = {}
    for t in tests:
        by_key.setdefault(t.key, []).append(t)
    rows = []
    for c in criteria(prd, story_ids):
        ts = by_key.get(c.key, [])
        if not ts:
            passed, ev = False, "no test claims this acceptance line"
        else:
            parts, ok = [], True
            for t in ts:
                label = f"{t.cls}.{t.name}"
                if t.source_set == "androidTest":
                    ok = False
                    parts.append(f"{label}: androidTest not executed (needs an emulator)")
                    continue
                st, detail = results.get((t.full_class, t.name), ("missing", ""))
                if st != "passed":
                    ok = False
                parts.append(f"{label}: {st}" + (f" ({detail})" if detail else "")
                             + (f" [{unit_note}]" if st == "missing" and unit_note else ""))
            passed, ev = ok, "; ".join(parts)
        rows.append({"story_id": c.story_id, "line": c.line, "passed": passed and build_green,
                     "evidence": _ev(ev if build_green else "build not green; " + ev)})
    return {"task_id": task_id, "build_green": build_green, "fix_rounds": min(fix_rounds, 5), "criteria": rows}


def write_tests(runner: AgentRunner, inputs: dict[str, Any], editor: EditThenLint,
                feedback: list[str] | None = None) -> tuple[dict[str, Any], list[TestRef]]:
    """Model -> verify -> edit-then-lint. Lint rejection rolls back and raises AgentOutputError."""
    doc = runner.run(TEST_ENGINEER, inputs, feedback)
    links = [m for f in doc["files"] for m in symlink_errors(editor.workspace, f["path"])]
    if links:
        raise AgentOutputError(links)
    res = editor.apply({f["path"]: f["content"] for f in doc["files"]})
    if not res.applied:
        raise AgentOutputError([f"lint: {m}" for m in res.lint.messages] or ["lint failed"])
    return doc, parse_tests(doc["files"])[0]


def execute_tests(inputs: dict[str, Any], refs: list[TestRef], gradle: GradleRunner, project: Path, task_id: str,
                  build_green: bool, fix_rounds: int = 0, schemas: SchemaRegistry | None = None) -> tuple[dict[str, Any], bool]:
    """Run the JVM unit tests, read JUnit XML, build the schema-checked report. Returns (report, executed)."""
    results_dir = (Path(project) / module_dir(app_module(inputs["module_graph"]) or ":app")
                   / "build" / "test-results" / "testDebugUnitTest")
    if build_green:  # old XML from an earlier round must never count as evidence for this run
        shutil.rmtree(results_dir, ignore_errors=True)
    unit = gradle.run(project, "testDebugUnitTest") if build_green else None
    results = parse_junit_dir(results_dir) if build_green else {}
    note = "" if results else "no JUnit results on disk" + (
        f"; gradle: {(unit.errors or ('failed',))[0]}" if unit is not None and not unit.ok else "")
    report = build_report(task_id, inputs["prd"], refs, results, build_green, fix_rounds, inputs.get("story_ids"), note)
    errs = (schemas or SchemaRegistry()).errors("test-report", report)
    if errs:  # a bug in this module, not in the model: do not hand an invalid report downstream
        raise RuntimeError(f"internal error: test report invalid: {errs}")
    return report, bool(results)


@dataclass
class TestEngineerResult:
    __test__ = False
    change: dict[str, Any]
    report: dict[str, Any]
    tests: list[TestRef]
    executed: bool       # JUnit results were found on disk


def run_test_engineer(runner: AgentRunner, inputs: dict[str, Any], editor: EditThenLint, gradle: GradleRunner,
                      project: Path, task_id: str, feedback: list[str] | None = None, fix_rounds: int = 0,
                      schemas: SchemaRegistry | None = None) -> TestEngineerResult:
    """write_tests -> assembleDebug -> execute_tests (no Build Doctor here; the pipeline adds it)."""
    doc, refs = write_tests(runner, inputs, editor, feedback)
    build = gradle.run(project, "assembleDebug")
    report, executed = execute_tests(inputs, refs, gradle, project, task_id, build.ok, fix_rounds, schemas)
    return TestEngineerResult(doc, report, refs, executed)
