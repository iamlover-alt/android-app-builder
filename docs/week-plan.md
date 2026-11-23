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
- [ ] Day 1: Orchestrator runtime (`appbuilder/orchestrator/`): task DAG, artifact-ready triggers, JSON-schema validation of handoffs, 5-round fix cap with escalation, run log. Unit tests.
- [ ] Day 2: Tool layer (`appbuilder/tools/`): edit-then-lint with rollback, gradle-run, emulator-run, behind interfaces with fakes. Sandbox `Dockerfile` (JDK 17+, Android SDK API 36, warm Gradle daemon).
- [ ] Day 3: Agent runner (`appbuilder/agents/`) calling the Anthropic API with each agent's spec as system prompt; implement Product Strategist and Android Architect end to end (PRD and module graph validate against schemas).
- [ ] Day 4: UI Engineer, Domain/Data Engineer, Build Doctor with failure memory (error signature -> fix store).
- [ ] Day 5: Test Engineer (Gherkin to tests), Memory Keeper context packs, benchmark harness (`benchmark/run.py`) appending to run records; run specs 01-05.
- [ ] Day 6: CLI (`appbuilder new`, `status`, `approve`) with gates 1-3; run specs 06-10; triage failures into docs/failures.md and ADRs.
- [ ] Day 7: Hardening (budget caps, secrets never in prompts, dependency allowlist), quickstart README, benchmark report `docs/benchmark-report-v0.1.md`, tag `v0.1.0`.

## Known gaps
(append here)
