"""Android Architect: PRD -> module graph (schemas/module-graph.schema.json)."""
from __future__ import annotations

import json
from typing import Any

from .runner import AgentDef, wrap_untrusted

# layer -> layers it may depend on (checked deterministically; no same-layer edges, so the graph is acyclic)
ALLOWED = {
    "app": {"ui", "domain", "data", "core"},
    "ui": {"domain", "core"},
    "domain": {"core"},
    "data": {"domain", "core"},
    "core": set(),
}

RULES = (
    "Rules: Kotlin + Compose, Hilt DI, target API 36 or higher. Exactly one module with layer `app` "
    "(path `:app`). Module paths are unique and start with ':'. depends_on lists module paths that exist. "
    "Allowed dependencies by layer: app -> ui, domain, data, core; ui -> domain, core; domain -> core; "
    "data -> domain, core; core -> nothing. (This layer rule also makes cycles impossible.) adrs lists short decision titles.\n")


def build_user(inputs: dict[str, Any]) -> str:
    return "Design the module graph for this PRD.\n" + wrap_untrusted("prd", json.dumps(inputs["prd"], indent=1))


def verify(graph: Any, inputs: dict[str, Any]) -> list[str]:
    mods = graph["modules"]
    errs: list[str] = []
    paths = [m["path"] for m in mods]
    errs += [f"duplicate module path {p!r}" for p in sorted({p for p in paths if paths.count(p) > 1})]
    errs += [f"module path {p!r} must start with ':'" for p in paths if not p.startswith(":")]
    if sum(m["layer"] == "app" for m in mods) != 1:
        errs.append("exactly one module with layer 'app' is required")
    layer = {m["path"]: m["layer"] for m in mods}
    for m in mods:
        for d in m["depends_on"]:
            if d not in layer:
                errs.append(f"{m['path']}: depends on unknown module {d!r}")
            elif layer[d] not in ALLOWED[m["layer"]]:
                errs.append(f"{m['path']}: layer {m['layer']} may not depend on {d} (layer {layer[d]})")
    return errs


ANDROID_ARCHITECT = AgentDef("android-architect", "module-graph", build_user, verify, RULES)
