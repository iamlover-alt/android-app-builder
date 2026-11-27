"""Goal -> PRD -> module graph -> tests (written first) -> data code -> UI code -> build/doctor -> test report.

One task per agent in an Orchestrator graph; handoffs are schema-validated artifacts. Tests are written
before the code they cover (the Test Engineer only needs the PRD and module graph). Memory Keeper context
packs are injected into each agent call. The model client and Gradle runner are injected, so the same
pipeline runs against fakes offline (benchmark default) or real services later.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .agents import (BUILD_DOCTOR, DATA_ENGINEER, UI_ENGINEER, AgentRunner, BuildDoctor, FailureMemory,
                     ModelClient, ProjectGraph, build_pack, run_code_agent, verify_pack)
from .agents.runner import AgentOutputError
from .agents.test_engineer import execute_tests, write_tests
from .orchestrator import Orchestrator, RunLog, RunResult, SchemaRegistry, Task, TaskGraph
from .tools import EditThenLint, FakeLinter, GradleRunner, Linter

OPAQUE = {"test-suite", "data-change", "ui-change"}


@dataclass
class Pipeline:
    client: ModelClient
    gradle: GradleRunner
    project: Path
    linter: Linter = field(default_factory=FakeLinter)
    memory: FailureMemory = field(default_factory=FailureMemory)
    log: RunLog = field(default_factory=RunLog)
    schemas: SchemaRegistry = field(default_factory=SchemaRegistry)
    pack_errors: list[str] = field(default_factory=list)   # context-pack verification problems (should stay empty)

    def __post_init__(self) -> None:
        self.project = Path(self.project)
        self.project.mkdir(parents=True, exist_ok=True)
        self.runner = AgentRunner(self.client, self.schemas, log=self.log)
        self.editor = EditThenLint(self.project, self.linter)
        self._done: dict[str, dict[str, Any]] = {}   # task id -> stories already applied (resume after a fix round)
        self.doctor_reports: list[Any] = []

    # -- context packs --------------------------------------------------------
    def _context(self, agent: str, prd: dict | None, mg: dict | None, **focus: Any) -> str:
        g = ProjectGraph.build(prd, mg, self.memory)
        pack = build_pack(g, agent, **focus)
        self.pack_errors += verify_pack(pack, g)
        return pack.render()

    # -- agent functions (orchestrator AgentFn signature) -----------------------
    def _prd(self, task: Task, inputs: dict, feedback: list[str]) -> dict:
        from .agents import PRODUCT_STRATEGIST
        return {"prd": self.runner.run(PRODUCT_STRATEGIST, {"goal": inputs["goal"]}, feedback or None)}

    def _arch(self, task: Task, inputs: dict, feedback: list[str]) -> dict:
        from .agents import ANDROID_ARCHITECT
        ctx = self._context("android-architect", inputs["prd"], None)
        return {"module-graph": self.runner.run(ANDROID_ARCHITECT, {"prd": inputs["prd"], "context": ctx}, feedback or None)}

    def _tests(self, task: Task, inputs: dict, feedback: list[str]) -> dict:
        prd, mg = inputs["prd"], inputs["module-graph"]
        ctx = self._context("test-engineer", prd, mg)
        doc, refs = write_tests(self.runner, {"prd": prd, "module_graph": mg, "context": ctx}, self.editor, feedback or None)
        return {"test-suite": {"change": doc, "tests": [r.__dict__ for r in refs]}}

    def _code(self, kind: str, task: Task, inputs: dict, feedback: list[str]) -> dict:
        prd, mg = inputs["prd"], inputs["module-graph"]
        layer, agent, name = ("data", DATA_ENGINEER, "data-engineer") if kind == "data" else ("ui", UI_ENGINEER, "ui-engineer")
        module = next((m["path"] for m in mg["modules"] if m["layer"] == layer), None)
        if module is None:
            raise AgentOutputError([f"module graph has no {layer} module"])
        done = self._done.setdefault(task.id, {})
        for sid in prd["mvp_cut"]:
            if sid in done:
                continue
            story = next(s for s in prd["stories"] if s["id"] == sid)
            ctx = self._context(name, prd, mg, story=sid, module=module)
            doc, _ = run_code_agent(self.runner, agent, {"module": module, "module_graph": mg, "story": story,
                                                         "context": ctx}, self.editor, feedback or None)
            done[sid] = doc
            feedback = []   # the feedback concerned the story that just succeeded on retry
        return {f"{kind}-change": {"changes": list(done.values())}}

    def _run_tests(self, task: Task, inputs: dict, feedback: list[str]) -> dict:
        prd, mg, suite = inputs["prd"], inputs["module-graph"], inputs["test-suite"]
        from .agents.test_engineer import TestRef
        refs = [TestRef(**t) for t in suite["tests"]]
        doctor = BuildDoctor(self.runner, self.memory, self.gradle, self.editor, self.project)
        rep = doctor.fix()
        self.doctor_reports.append(rep)
        report, executed = execute_tests({"prd": prd, "module_graph": mg}, refs, self.gradle, self.project,
                                         task.id, rep.green, rep.rounds, self.schemas)
        self.executed = executed
        return {"test-report": report}

    # -- run ------------------------------------------------------------------
    def run(self, goal: str) -> RunResult:
        self.executed = False
        graph = TaskGraph([
            Task("prd", "product-strategist", ["goal"], ["prd"]),
            Task("arch", "android-architect", ["prd"], ["module-graph"]),
            Task("tests", "test-engineer", ["prd", "module-graph"], ["test-suite"]),
            Task("data", "data-engineer", ["prd", "module-graph", "test-suite"], ["data-change"]),
            Task("ui", "ui-engineer", ["prd", "module-graph", "data-change"], ["ui-change"]),
            Task("verify", "build-doctor", ["prd", "module-graph", "test-suite", "ui-change"], ["test-report"]),
        ], external={"goal"})
        agents = {"product-strategist": self._prd, "android-architect": self._arch, "test-engineer": self._tests,
                  "data-engineer": lambda t, i, f: self._code("data", t, i, f),
                  "ui-engineer": lambda t, i, f: self._code("ui", t, i, f),
                  "build-doctor": self._run_tests}
        orch = Orchestrator(graph, agents, self.schemas, self.log, opaque=OPAQUE)
        orch.seed("goal", goal)
        return orch.run()
