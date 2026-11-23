"""Task DAG: tasks declare input/output artifact names; edges are derived from them."""
from __future__ import annotations

from dataclasses import dataclass, field

MAX_FIX_ROUNDS = 5
STATUSES = ("pending", "running", "blocked", "done", "escalated")


class GraphError(ValueError):
    pass


@dataclass
class Task:
    id: str
    agent: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    status: str = "pending"
    fix_rounds: int = 0

    def to_record(self) -> dict:
        """Dict conforming to schemas/task.schema.json."""
        return {
            "id": self.id,
            "agent": self.agent,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "status": self.status,
            "fix_rounds": self.fix_rounds,
        }


class TaskGraph:
    def __init__(self, tasks: list[Task], external: set[str] | None = None) -> None:
        """`external` = artifacts supplied from outside (e.g. the goal)."""
        self.tasks: dict[str, Task] = {}
        self.external = set(external or ())
        self.producer: dict[str, str] = {}
        for t in tasks:
            if t.id in self.tasks:
                raise GraphError(f"duplicate task id {t.id!r}")
            self.tasks[t.id] = t
            for a in t.outputs:
                if a in self.producer:
                    raise GraphError(f"artifact {a!r} produced by both {self.producer[a]!r} and {t.id!r}")
                if a in self.external:
                    raise GraphError(f"artifact {a!r} is external but also produced by {t.id!r}")
                self.producer[a] = t.id
        for t in tasks:
            for a in t.inputs:
                if a not in self.producer and a not in self.external:
                    raise GraphError(f"task {t.id!r} needs {a!r}, which nothing produces")
        self.order = self._toposort()

    def deps(self, task_id: str) -> set[str]:
        return {self.producer[a] for a in self.tasks[task_id].inputs if a in self.producer}

    def dependents(self, task_id: str) -> set[str]:
        return {t.id for t in self.tasks.values() if task_id in self.deps(t.id)}

    def _toposort(self) -> list[str]:
        indeg = {i: len(self.deps(i)) for i in self.tasks}
        ready = sorted(i for i, d in indeg.items() if d == 0)
        out: list[str] = []
        while ready:
            n = ready.pop(0)
            out.append(n)
            for m in sorted(self.dependents(n)):
                indeg[m] -= 1
                if indeg[m] == 0:
                    ready.append(m)
        if len(out) != len(self.tasks):
            cyc = sorted(set(self.tasks) - set(out))
            raise GraphError(f"cycle among tasks: {cyc}")
        return out

    def descendants(self, task_id: str) -> set[str]:
        seen: set[str] = set()
        stack = [task_id]
        while stack:
            for d in self.dependents(stack.pop()):
                if d not in seen:
                    seen.add(d)
                    stack.append(d)
        return seen
