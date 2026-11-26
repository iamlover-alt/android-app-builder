"""Product Strategist: goal text -> PRD (schemas/prd.schema.json)."""
from __future__ import annotations

import re
from typing import Any

from .runner import AgentDef, wrap_untrusted

GHERKIN = re.compile(r"^\s*(Given|When|Then|And|But)\b", re.I)

RULES = (
    "Rules: cut scope to an MVP (3 to 7 stories); mvp_cut lists story ids; every story has at least one "
    "acceptance line written as Gherkin (Given/When/Then/And); target_sdk is 36 or higher; story ids are "
    "unique like s1, s2.\n")


def build_user(inputs: dict[str, Any]) -> str:
    return "Write the PRD for this app idea.\n" + wrap_untrusted("goal", str(inputs["goal"]))


def verify(prd: Any, inputs: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    ids = [s["id"] for s in prd["stories"]]
    if not ids:
        errs.append("stories: at least one story is required")
    errs += [f"stories: duplicate id {i!r}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    for s in prd["stories"]:
        if not s["acceptance"]:
            errs.append(f"story {s['id']}: needs at least one acceptance line")
        errs += [f"story {s['id']}: acceptance line is not Gherkin: {a[:60]!r}"
                 for a in s["acceptance"] if not GHERKIN.match(a)]
    if not prd["mvp_cut"]:
        errs.append("mvp_cut: must contain at least one story id")
    errs += [f"mvp_cut: unknown story id {i!r}" for i in prd["mvp_cut"] if i not in ids]
    if "min_sdk" in prd and "target_sdk" in prd and prd["min_sdk"] > prd["target_sdk"]:
        errs.append("min_sdk must not exceed target_sdk")
    return errs


PRODUCT_STRATEGIST = AgentDef("product-strategist", "prd", build_user, verify, RULES)
