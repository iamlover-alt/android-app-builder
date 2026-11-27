"""Memory Keeper (Phase 1): the Project Graph index and per-agent context packs.

Deterministic, no model calls. The graph holds quotable facts, each under a source id:

    prd:s1            story summary          prd:s1#2   one acceptance line (1-based)
    mg:<module path>  module, layer, deps    mg:adr1    architecture decision title
    fail:<signature>  known fix from failure memory

A context pack is a list of claims. A claim's text is copied verbatim from the graph entry it cites,
so a claim cannot say anything its source does not. `build_pack` drops optional claims (lowest priority
first) until the pack fits the agent's token budget and raises PackTooLarge if the required claims alone
do not fit. `verify_pack` re-checks citations, verbatim text and budget.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .memory import FailureMemory, signature
from .runner import wrap_untrusted

# Tokens each agent may spend on injected context (a share of its window, not the window itself).
BUDGETS = {"product-strategist": 1500, "android-architect": 4000, "ui-engineer": 6000, "data-engineer": 6000,
           "test-engineer": 6000, "build-doctor": 3000}
DEFAULT_BUDGET = 3000


def estimate_tokens(text: str) -> int:
    """Rough upper estimate (4 chars per token, rounded up, plus line overhead). No tokenizer offline."""
    return -(-len(text) // 4) + 2


class PackTooLarge(ValueError):
    pass


@dataclass(frozen=True)
class Claim:
    text: str
    source: str
    priority: int = 5        # lower = kept longer
    required: bool = False


@dataclass
class ContextPack:
    agent: str
    budget: int
    claims: list[Claim] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)    # source ids left out for size

    def tokens(self) -> int:
        return sum(estimate_tokens(self.line(c)) for c in self.claims)

    @staticmethod
    def line(c: Claim) -> str:
        return f"- {c.text} [source: {c.source}]"

    def render(self) -> str:
        body = "\n".join(self.line(c) for c in self.claims)
        return wrap_untrusted(f"context-pack-{self.agent}", body)  # artifact text came from a model: data, not orders


class ProjectGraph:
    def __init__(self) -> None:
        self.sources: dict[str, str] = {}
        self.kinds: dict[str, str] = {}
        self.modules: dict[str, dict[str, Any]] = {}
        self.stories: dict[str, dict[str, Any]] = {}
        self.mvp: list[str] = []

    def add(self, source: str, kind: str, text: str) -> None:
        if source in self.sources:
            raise ValueError(f"duplicate source id {source!r}")
        self.sources[source] = " ".join(text.split())
        self.kinds[source] = kind

    def add_prd(self, prd: dict[str, Any]) -> None:
        self.mvp = list(prd["mvp_cut"])
        for s in prd["stories"]:
            sid = s["id"]
            self.stories[sid] = s
            self.add(f"prd:{sid}", "story", f"Story {sid}: as a {s['as_a']}, I want {s['i_want']}, so that {s['so_that']}")
            for i, line in enumerate(s["acceptance"], 1):
                self.add(f"prd:{sid}#{i}", "acceptance", f"Acceptance {sid}#{i}: {line}")

    def add_module_graph(self, mg: dict[str, Any]) -> None:
        for m in mg["modules"]:
            self.modules[m["path"]] = m
            deps = ", ".join(m["depends_on"]) or "nothing"
            self.add(f"mg:{m['path']}", "module", f"Module {m['path']} (layer {m['layer']}) depends on {deps}")
        for i, a in enumerate(mg.get("adrs", []), 1):
            self.add(f"mg:adr{i}", "adr", f"Decision: {a}")

    def add_failures(self, memory: FailureMemory) -> None:
        for e in memory.entries.values():
            if e.usable():
                self.add(f"fail:{e.signature}", "failure", f"Known build failure '{e.sample}': {e.diagnosis}")

    @classmethod
    def build(cls, prd: dict[str, Any] | None = None, module_graph: dict[str, Any] | None = None,
              memory: FailureMemory | None = None) -> "ProjectGraph":
        g = cls()
        if prd:
            g.add_prd(prd)
        if module_graph:
            g.add_module_graph(module_graph)
        if memory:
            g.add_failures(memory)
        return g

    def index(self) -> dict[str, str]:
        """source id -> kind, for humans and for citation checks."""
        return dict(self.kinds)


def _story_claims(g: ProjectGraph, ids: Iterable[str], required: bool) -> list[Claim]:
    out = []
    for sid in ids:
        if sid not in g.stories:
            raise KeyError(f"unknown story {sid!r}")
        out.append(Claim(g.sources[f"prd:{sid}"], f"prd:{sid}", 1, required))
        out += [Claim(g.sources[f"prd:{sid}#{i}"], f"prd:{sid}#{i}", 1, required)
                for i in range(1, len(g.stories[sid]["acceptance"]) + 1)]
    return out


def _module_claims(g: ProjectGraph, module: str, with_deps: bool) -> list[Claim]:
    if module not in g.modules:
        raise KeyError(f"unknown module {module!r}")
    out = [Claim(g.sources[f"mg:{module}"], f"mg:{module}", 1, True)]
    if with_deps:
        out += [Claim(g.sources[f"mg:{d}"], f"mg:{d}", 3) for d in g.modules[module]["depends_on"] if f"mg:{d}" in g.sources]
    return out


def _adr_claims(g: ProjectGraph) -> list[Claim]:
    return [Claim(t, s, 4) for s, t in g.sources.items() if g.kinds[s] == "adr"]


def _failure_claims(g: ProjectGraph, errors: list[str] | None) -> list[Claim]:
    sid = f"fail:{signature(errors)}" if errors else None
    return [Claim(g.sources[sid], sid, 2)] if sid in g.sources else []


def select(g: ProjectGraph, agent: str, story: str | None = None, module: str | None = None,
           errors: list[str] | None = None) -> list[Claim]:
    """What each agent is told. `story`/`module`/`errors` narrow the pack to the task at hand."""
    mvp = g.mvp
    if agent == "product-strategist":
        return _adr_claims(g)
    if agent == "android-architect":
        return _story_claims(g, mvp, True) + _adr_claims(g)
    if agent in ("ui-engineer", "data-engineer"):
        if not (story and module):
            raise ValueError(f"{agent} pack needs story and module")
        return (_story_claims(g, [story], True) + _module_claims(g, module, True) + _adr_claims(g)
                + (_failure_claims(g, errors) if agent == "data-engineer" else []))
    if agent == "test-engineer":
        app = next((m for m, d in g.modules.items() if d["layer"] == "app"), None)
        return _story_claims(g, [story] if story else mvp, True) + (_module_claims(g, app, True) if app else [])
    if agent == "build-doctor":
        return _failure_claims(g, errors) + (_module_claims(g, module, False) if module else [])
    raise ValueError(f"no context pack defined for agent {agent!r}")


def build_pack(g: ProjectGraph, agent: str, budget: int | None = None, **focus: Any) -> ContextPack:
    budget = budget or BUDGETS.get(agent, DEFAULT_BUDGET)
    seen: set[str] = set()
    claims = [c for c in select(g, agent, **focus) if not (c.source in seen or seen.add(c.source))]
    pack = ContextPack(agent, budget, claims)
    required = sum(estimate_tokens(ContextPack.line(c)) for c in claims if c.required)
    if required > budget:
        raise PackTooLarge(f"{agent}: required context needs ~{required} tokens, budget is {budget}")
    while pack.tokens() > budget:
        victim = max((c for c in pack.claims if not c.required), key=lambda c: c.priority, default=None)
        if victim is None:  # unreachable: required alone fits
            raise PackTooLarge(f"{agent}: cannot fit pack in {budget} tokens")
        # drop the last claim of the least important priority
        last = [c for c in pack.claims if c.priority == victim.priority and not c.required][-1]
        pack.claims.remove(last)
        pack.dropped.append(last.source)
    return pack


def verify_pack(pack: ContextPack, g: ProjectGraph) -> list[str]:
    """Every claim cites a graph source, quotes it verbatim, and the pack fits its budget."""
    errs = []
    for c in pack.claims:
        if c.source not in g.sources:
            errs.append(f"claim cites unknown source {c.source!r}")
        elif c.text != g.sources[c.source]:
            errs.append(f"claim for {c.source} does not match its source text")
    if pack.tokens() > pack.budget:
        errs.append(f"pack is ~{pack.tokens()} tokens, over budget {pack.budget}")
    return errs
