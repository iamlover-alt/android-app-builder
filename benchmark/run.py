#!/usr/bin/env python3
"""Benchmark harness: run the Phase 1 pipeline on benchmark specs and append to each spec's run record.

    python benchmark/run.py --specs 01-05            # default model: real if ANTHROPIC_API_KEY is set, else fake
    python benchmark/run.py --specs 01,03 --model fake --no-record

What a row means depends on the columns marked "fake": with the fake model the stories and code are
templates, and with fake Gradle nothing is compiled or executed, so green build and acceptance pass
rate are reported as n/a, never as passes. The harness only records what actually happened.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from appbuilder.agents import AnthropicClient, FakeModelClient, ModelError  # noqa: E402
from appbuilder.agents.test_engineer import criteria  # noqa: E402
from appbuilder.pipeline import Pipeline  # noqa: E402
from appbuilder.tools import FakeGradle  # noqa: E402

SPEC_DIR = Path(__file__).resolve().parent / "specs"
HEADER = "| Date | Builder commit | Green build | Acceptance pass % | Interventions | Cost | Notes |"
RECORD_HEADING = "## Run record"


@dataclass
class Spec:
    path: Path
    title: str
    idea: str
    stresses: str


def parse_spec(path: Path) -> Spec:
    text = path.read_text(encoding="utf-8")
    title = re.search(r"^#\s+(.+)$", text, re.M)
    idea = re.search(r"\*\*One-line idea:\*\*\s*(.+)", text)
    stress = re.search(r"\*\*Stresses:\*\*\s*(.+)", text)
    if not (title and idea):
        raise ValueError(f"{path.name}: spec needs a '# title' and a '**One-line idea:**' line")
    return Spec(path, title.group(1).strip(), idea.group(1).strip(), stress.group(1).strip() if stress else "")


def select_specs(arg: str, spec_dir: Path = SPEC_DIR) -> list[Path]:
    files = sorted(spec_dir.glob("[0-9][0-9]-*.md"))
    by_num = {f.name[:2]: f for f in files}
    if arg == "all":
        return files
    wanted: list[str] = []
    for part in arg.split(","):
        m = re.fullmatch(r"(\d{2})-(\d{2})", part.strip())
        if m:
            wanted += [f"{n:02d}" for n in range(int(m[1]), int(m[2]) + 1)]
        elif re.fullmatch(r"\d{2}", part.strip()):
            wanted.append(part.strip())
        else:
            raise ValueError(f"bad spec selector {part!r} (use 01-05, 01,03 or all)")
    missing = [w for w in wanted if w not in by_num]
    if missing:
        raise ValueError(f"no spec for number(s): {missing}")
    return [by_num[w] for w in wanted]


def builder_commit(repo: Path = ROOT) -> str:
    def git(*a: str) -> str:
        return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, timeout=30, check=True).stdout.strip()
    try:
        sha = git("rev-parse", "--short", "HEAD")
        return sha + ("-dirty" if git("status", "--porcelain", "--untracked-files=no") else "")
    except (OSError, subprocess.SubprocessError):
        return "unknown"


@dataclass
class Result:
    spec: str
    model: str            # "fake" or "anthropic"
    tools: str            # "fake"
    pipeline_ok: bool
    failed_tasks: list[str] = field(default_factory=list)
    escalations: int = 0
    fix_rounds: int = 0
    model_calls: int = 0
    criteria: int = 0
    tests_mapped: int = 0
    tests_executed: bool = False
    acceptance_passed: int = 0
    build_green: bool | None = None
    build_real: bool = False
    seconds: float = 0.0
    pack_errors: list[str] = field(default_factory=list)
    report: dict | None = None
    notes: str = ""


def run_spec(spec: Spec, client, model_kind: str, workdir: Path) -> Result:
    t0 = time.monotonic()
    pipe = Pipeline(client, FakeGradle(), workdir / "project")
    res = pipe.run(spec.idea)
    r = Result(spec.path.name[:2], model_kind, "fake", res.ok)
    r.seconds = round(time.monotonic() - t0, 2)
    r.failed_tasks = sorted(i for i, t in res.tasks.items() if t.status != "done")
    r.escalations = len(res.escalations)
    r.fix_rounds = sum(t.fix_rounds for t in res.tasks.values())
    r.model_calls = len(pipe.log.of("model_call"))
    r.pack_errors = pipe.pack_errors
    report = res.artifacts.get("test-report")
    suite = res.artifacts.get("test-suite")
    prd = res.artifacts.get("prd")
    if prd:
        want = {c.key for c in criteria(prd)}
        r.criteria = len(want)
        if suite:
            r.tests_mapped = len(want & {t["key"] for t in suite["tests"]})
    if report:
        r.report = report
        r.tests_executed = pipe.executed
        r.acceptance_passed = sum(c["passed"] for c in report["criteria"])
        r.build_green = report["build_green"]
    return r


def row_for(r: Result, commit: str, today: str | None = None) -> str:
    fake_model, fake_tools = r.model == "fake", r.tools == "fake"
    green = "n/a (fake Gradle, nothing compiled)" if fake_tools else ("yes" if r.build_green else "no")
    if r.tests_executed:
        acc = f"{r.acceptance_passed}/{r.criteria} = {100 * r.acceptance_passed // max(r.criteria, 1)}%"
    else:
        acc = f"n/a (0 of {r.criteria} tests executed)"
    interventions = f"{r.escalations} escalated" + (f" ({', '.join(r.failed_tasks)})" if r.failed_tasks else "")
    cost = "$0 (fake model)" if fake_model else "n/a (token usage not recorded)"
    bits = [f"{'FAKE' if fake_model else 'real'} model, {'FAKE' if fake_tools else 'real'} Gradle/emulator"
            + (": wiring check only" if fake_model or fake_tools else ""),
            f"pipeline {'ok' if r.pipeline_ok else 'FAILED'}", f"{r.model_calls} model calls", f"{r.fix_rounds} fix rounds",
            f"{r.tests_mapped}/{r.criteria} acceptance lines have a test"]
    if fake_model:
        bits.append("stories/code are templates and tests are failing placeholders")
    if r.pack_errors:
        bits.append(f"{len(r.pack_errors)} context-pack problems")
    bits.append(f"{r.seconds}s wall-clock")
    cells = [today or date.today().isoformat(), commit, green, acc, interventions, cost, "; ".join(bits)]
    return "| " + " | ".join(re.sub(r"\s+", " ", c.replace("|", "/")).strip()[:400] for c in cells) + " |"


def append_run_record(spec_path: Path, row: str) -> None:
    lines = spec_path.read_text(encoding="utf-8").splitlines()
    try:
        h = next(i for i, l in enumerate(lines) if l.strip() == RECORD_HEADING)
    except StopIteration:
        lines += ["", RECORD_HEADING, HEADER, "| --- | --- | --- | --- | --- | --- | --- |"]
        h = len(lines) - 3
    last = h
    for i in range(h + 1, len(lines)):
        if lines[i].startswith("|"):
            last = i
        elif lines[i].startswith("## "):
            break
    if last == h:
        raise ValueError(f"{spec_path.name}: '{RECORD_HEADING}' has no table")
    lines.insert(last + 1, row)
    spec_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_client(choice: str):
    key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    kind = ("anthropic" if key else "fake") if choice == "auto" else choice
    if kind == "anthropic":
        return AnthropicClient(), "anthropic"   # raises ModelError if no key
    return FakeModelClient(), "fake"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--specs", default="01-05")
    ap.add_argument("--model", choices=["auto", "fake", "anthropic"], default="auto")
    ap.add_argument("--tools", choices=["fake", "real"], default="fake")
    ap.add_argument("--no-record", action="store_true", help="do not append to the run records")
    ap.add_argument("--runs-dir", default=str(ROOT / "runs" / "benchmark"))
    a = ap.parse_args(argv)
    if a.tools == "real":
        print("--tools real is not available yet: it needs the sandbox image (Android SDK, emulator) and the app "
              "templates; see docs/week-plan.md Known gaps.", file=sys.stderr)
        return 2
    try:
        paths = select_specs(a.specs)
        client, kind = make_client(a.model)
    except (ValueError, ModelError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    commit = builder_commit()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = Path(a.runs_dir) / stamp
    results = []
    for p in paths:
        spec = parse_spec(p)
        r = run_spec(spec, client, kind, out / p.stem)
        results.append(r)
        if not a.no_record:
            append_run_record(p, row_for(r, commit))
        print(f"{p.stem}: pipeline {'ok' if r.pipeline_ok else 'FAILED ' + str(r.failed_tasks)}, "
              f"{r.tests_mapped}/{r.criteria} lines mapped, executed={r.tests_executed}, {r.seconds}s ({kind} model, fake tools)")
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps([asdict(r) for r in results], indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
