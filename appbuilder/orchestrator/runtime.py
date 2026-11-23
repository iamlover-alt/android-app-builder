"""Orchestrator runtime.

A task starts when every input artifact exists (artifact-ready trigger). Its
outputs are validated against schemas/<artifact>.schema.json before they are
published; a failed handoff is a fix round. After MAX_FIX_ROUNDS failed fix
rounds the task is escalated with the failing evidence and its descendants are
blocked. Agents never talk to each other: they only read/write artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .dag import MAX_FIX_ROUNDS, Task, TaskGraph
from .runlog import RunLog, clip
from .schemas import SchemaRegistry

# agent(task, inputs, feedback) -> {artifact_name: json_value}
# `feedback` is the list of errors from the previous failed round (empty on first try).
AgentFn = Callable[[Task, dict[str, Any], list[str]], dict[str, Any]]


@dataclass
class Escalation:
    task_id: str
    agent: str
    rounds: int
    evidence: list[str]


@dataclass
class RunResult:
    artifacts: dict[str, Any]
    tasks: dict[str, Task]
    escalations: list[Escalation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(t.status == "done" for t in self.tasks.values())


class Orchestrator:
    def __init__(
        self,
        graph: TaskGraph,
        agents: dict[str, AgentFn],
        schemas: SchemaRegistry | None = None,
        log: RunLog | None = None,
        opaque: set[str] | None = None,
        max_fix_rounds: int = MAX_FIX_ROUNDS,
    ) -> None:
        if max_fix_rounds > MAX_FIX_ROUNDS:
            raise ValueError(f"max_fix_rounds cannot exceed {MAX_FIX_ROUNDS}")
        self.graph = graph
        self.agents = agents
        self.schemas = schemas or SchemaRegistry()
        self.log = log or RunLog()
        self.opaque = set(opaque or ())  # artifacts deliberately without a schema (files, logs)
        self.max_fix_rounds = max_fix_rounds
        self.artifacts: dict[str, Any] = {}
        self.escalations: list[Escalation] = []
        for t in graph.tasks.values():
            if t.agent not in agents:
                raise ValueError(f"no agent registered for {t.agent!r} (task {t.id!r})")
            for a in t.outputs:
                if not self.schemas.has(a) and a not in self.opaque:
                    raise ValueError(f"artifact {a!r} has no schema and is not declared opaque")
        # task records must themselves satisfy task.schema.json
        self._check_record = self.schemas.has("task")

    # -- public API ---------------------------------------------------------
    def seed(self, name: str, value: Any) -> None:
        """Supply an external artifact (e.g. the goal)."""
        if name not in self.graph.external:
            raise ValueError(f"{name!r} is not declared external")
        self._publish(name, value, source="external")

    def run(self) -> RunResult:
        self.log.emit("run_start", tasks=self.graph.order)
        missing = sorted(a for a in self.graph.external if a not in self.artifacts)
        while True:
            task = self._next_ready()
            if task is None:
                break
            self._execute(task)
        for t in self.graph.tasks.values():
            if t.status == "pending":
                self._set(t, "blocked", reason=f"inputs never became ready (external missing: {missing})")
        result = RunResult(dict(self.artifacts), self.graph.tasks, list(self.escalations))
        self.log.emit("run_end", ok=result.ok, statuses={i: t.status for i, t in self.graph.tasks.items()})
        return result

    # -- internals ----------------------------------------------------------
    def _next_ready(self) -> Task | None:
        for tid in self.graph.order:  # deterministic: topological, then id order
            t = self.graph.tasks[tid]
            if t.status == "pending" and all(a in self.artifacts for a in t.inputs):
                return t
        return None

    def _set(self, t: Task, status: str, **fields: Any) -> None:
        t.status = status
        rec = t.to_record()
        if self._check_record:
            errs = self.schemas.errors("task", rec)
            assert not errs, f"task record invalid: {errs}"
        self.log.emit("task_status", task=t.id, agent=t.agent, status=status, fix_rounds=t.fix_rounds, **fields)

    def _publish(self, name: str, value: Any, source: str) -> None:
        self.artifacts[name] = value
        self.log.emit("artifact_ready", artifact=name, source=source)

    def _validate(self, t: Task, produced: Any) -> list[str]:
        if not isinstance(produced, dict):
            return [f"agent must return a dict of artifacts, got {type(produced).__name__}"]
        errs = [f"missing output artifact {a!r}" for a in t.outputs if a not in produced]
        errs += [f"undeclared output artifact {a!r}" for a in produced if a not in t.outputs]
        for a in t.outputs:
            if a in produced and self.schemas.has(a):
                errs += [f"{a}: {e}" for e in self.schemas.errors(a, produced[a])]
        return errs

    def _execute(self, t: Task) -> None:
        inputs = {a: self.artifacts[a] for a in t.inputs}
        self._set(t, "running")
        feedback: list[str] = []
        while True:
            self.log.emit("agent_call", task=t.id, agent=t.agent, attempt=t.fix_rounds + 1)
            try:
                produced = self.agents[t.agent](t, inputs, list(feedback))
                errs = self._validate(t, produced)
            except Exception as exc:  # agent crash counts as a failed round
                errs = [f"agent raised {type(exc).__name__}: {exc}"]
            if not errs:
                for a in t.outputs:
                    self._publish(a, produced[a], source=t.id)
                self._set(t, "done")
                return
            errs = [clip(e) for e in errs]
            self.log.emit("handoff_rejected", task=t.id, round=t.fix_rounds, errors=errs)
            if t.fix_rounds >= self.max_fix_rounds:
                self._escalate(t, errs)
                return
            t.fix_rounds += 1
            feedback = errs

    def _escalate(self, t: Task, evidence: list[str]) -> None:
        esc = Escalation(t.id, t.agent, t.fix_rounds, evidence)
        self.escalations.append(esc)
        self._set(t, "escalated", evidence=evidence)
        self.log.emit("escalation", task=t.id, agent=t.agent, rounds=t.fix_rounds, evidence=evidence)
        for d in sorted(self.graph.descendants(t.id)):
            dt = self.graph.tasks[d]
            if dt.status == "pending":
                self._set(dt, "blocked", reason=f"upstream {t.id} escalated")
