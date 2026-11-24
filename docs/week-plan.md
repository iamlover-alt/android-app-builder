# Week plan: Phase 1 to a usable v0.1

Target (end of day 7): `appbuilder new "<idea>"` produces a buildable Kotlin/Compose app from a prompt, passing its own generated tests, with three human gates, plus a benchmark report. Scope is the Phase 1 core loop (8 agents), not the full 94-role catalog.

Stack decision: see docs/decisions/0002-python-orchestrator.md.

Each day: read this file, do that day's work on a branch `day-N`, run tests, update the checklist and docs/failures.md, merge to main, push. If something cannot run in the cloud sandbox (no Android SDK, no emulator, no network), build it behind an interface with a fake, record the gap under "Known gaps" below, and continue.

## Who does what
| Agent (.claude/agents/) | Owns |
| --- | --- |
| builder-lead | Plans each day, delegates, integrates, ticks the checklist, pushes |
| runtime-engineer | Orchestrator runtime, CLI, gates (Days 1, 6) |
| sandbox-engineer | Tool layer, sandbox Dockerfile, app templates (Day 2) |
| agent-engineer | Agent runner and agents, failure memory, context packs (Days 3, 4, 5) |
| benchmark-engineer | Benchmark harness, run records, failure triage (Days 5, 6, 7) |
| critic-reviewer | Reviews every branch; blocks only with evidence |
| security-reviewer | Secrets, subprocesses, dependencies, prompt injection (all days, hardening on Day 7) |
| docs-release | README, ADRs, release notes, v0.1.0 tag (Day 7) |

## Checklist
- [x] Day 1: Orchestrator runtime (`appbuilder/orchestrator/`): task DAG, artifact-ready triggers, JSON-schema validation of handoffs, 5-round fix cap with escalation, run log. Unit tests.
- [x] Day 2: Tool layer (`appbuilder/tools/`): edit-then-lint with rollback, gradle-run, emulator-run, behind interfaces with fakes. Sandbox `Dockerfile` (JDK 17+, Android SDK API 36, warm Gradle daemon).
- [ ] Day 3: Agent runner (`appbuilder/agents/`) calling the Anthropic API with each agent's spec as system prompt; implement Product Strategist and Android Architect end to end (PRD and module graph validate against schemas).
- [ ] Day 4: UI Engineer, Domain/Data Engineer, Build Doctor with failure memory (error signature -> fix store).
- [ ] Day 5: Test Engineer (Gherkin to tests), Memory Keeper context packs, benchmark harness (`benchmark/run.py`) appending to run records; run specs 01-05.
- [ ] Day 6: CLI (`appbuilder new`, `status`, `approve`) with gates 1-3; run specs 06-10; triage failures into docs/failures.md and ADRs.
- [ ] Day 7: Hardening (budget caps, secrets never in prompts, dependency allowlist), quickstart README, benchmark report `docs/benchmark-report-v0.1.md`, tag `v0.1.0`.

## Known gaps
- Day 1: Gates (spec, design, release) are not in the runtime yet; they belong to Day 6 with the CLI. Human approval for release is therefore not enforced by code yet.
- Day 1: Tasks run sequentially, one at a time; no parallel execution, budgets or token/cost caps (Day 7).
- Day 1: Artifacts are validated only if a schema exists in schemas/ (prd, module-graph, task, test-report); other artifacts must be declared `opaque`. Only the shape is checked, not semantic correctness.
- Day 1: Nothing exercised against real agents or the Anthropic API; tests use fake agents only. No Android SDK, emulator or Play verification happened.
- Day 1: The cloud sandbox had no `add_repo`/`register_repo_root` tools; the repo was already cloned, so setup was skipped. Dev default Python is 3.13; tests were also run on 3.12.3 in a venv (ADR 0002 target) and pass.
- Day 1: Critic and security review agents were not run in this unattended session; branch is unreviewed.
- Day 2: No Android SDK, Gradle wrapper project, adb or emulator in the cloud sandbox; GradleTool and EmulatorTool are tested only against FakeRunner (argv, task whitelist, error parsing), never against a real build or emulator. Fakes report `verified_on_emulator=False`.
- Day 2: `sandbox/Dockerfile` was written but not built or run here (no Docker daemon check/build was performed); SDK version pins (cmdline-tools 11076708, build-tools 36.0.0, Gradle 8.13) and the API 36 system image name are unverified. The Gradle dependency cache warm-up needs a warmup project that arrives with the app templates; egress restriction to Maven Central/Google Maven is left to the runner, not enforced in the image.
- Day 2: Edit-then-lint rolls back via in-memory snapshots of the touched files only (not atomic against crashes mid-restore); CommandLinter assumes `ktlint` is on PATH in the sandbox. Gradle runs with `--offline`, so the first build needs a warmed cache.
- Day 2: Setup used the existing clone (no add_repo/register_repo_root tools available). Critic and security review agents were not run in this unattended session; branch is unreviewed.
