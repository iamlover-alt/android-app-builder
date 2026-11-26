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
- [x] Day 3: Agent runner (`appbuilder/agents/`) calling the Anthropic API with each agent's spec as system prompt; implement Product Strategist and Android Architect end to end (PRD and module graph validate against schemas).
- [x] Day 4: UI Engineer, Domain/Data Engineer, Build Doctor with failure memory (error signature -> fix store).
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
- Day 3: `AnthropicClient` (`appbuilder/agents/client.py`) has never made a real API call: the request shape, `anthropic-version` header, response parsing and default model id `claude-sonnet-5-5` are verified only against a local fake HTTP server. No `ANTHROPIC_API_KEY` was available or used.
- Day 3: The "recorded" model responses in `tests/fixtures/` are hand-written, not captured from a real model, so they prove schema/verifier wiring, not model quality. Product Strategist and Architect have not been run against a live model; the 3-to-7-story guidance is prompt-only, not enforced.
- Day 3: Architect's deterministic verifier checks layer rules, unknown/duplicate modules and a single `:app`; it does not build the skeleton or run lint (the spec's "skeleton builds" verifier belongs with templates/Gradle, not yet wired). ADR files and the skeleton repo are not generated yet (only ADR titles in `adrs`).
- Day 3: Prompt-injection defence is delimiting (`<untrusted>` tags, tag stripping) plus schema/verifier checks; agents have no tools. Client refuses non-https URLs (loopback excepted for tests) and does not follow redirects.
- Day 3: Critic and security-reviewer agents were run on this branch; their findings (delimiter bypass, URL/redirect hardening, dead cycle check, missing success-path test, missing docs) were fixed. Tests pass on Python 3.13 and 3.12.3.
- Day 4: Nothing ran against real Gradle, ktlint, Compose previews, Room or a live model: Build Doctor is tested with a scripted Gradle (red until a patch lands), FakeLinter and recorded model replies, so the fix loop is proven but not real compile errors. The UI/Data verifiers are regex checks (layer imports, `@Database` exportSchema/version/Migration, module path prefix), not compilation or a Room schema diff.
- Day 4: Failure memory keys on a coarse signature (paths, line numbers, quoted names and trailing identifiers are stripped), so different errors can share one entry; stored patches are exact find/replace on a path, so cross-project reuse only works when the file and text match, and a non-matching hit counts as a miss. One fix per signature, only the green-making step of a chain is recorded, the store is shared (not per project) and a human has not reviewed entries. Loaded entries are re-validated (path rules, secret scan) and a corrupt file is ignored.
- Day 4: Build Doctor may patch only `.kt/.java/.xml/.pro` under `src/` (or `proguard-rules.pro`). Gradle scripts, version catalogs and `gradle.properties` are refused, so dependency/AGP fixes escalate to a human; the Day 7 dependency allowlist is not built yet. Secret scan is pattern-based (Anthropic/GitHub/AWS keys, URL credentials, `password=`-style assignments) and cannot catch everything. Symlinks in patch/edit targets are rejected; `EditThenLint` itself still follows symlinks inside the workspace.
- Day 4: Round cap is 5 per Doctor run. A patch that leaves the same errors is reverted; a patch that changes the errors is kept, so an escalated run can leave partial patches (`DoctorReport.patched`/`dirty`). The UI/Data agents are not yet wired into a task graph (Day 5/6).
- Day 4: critic-reviewer and security-reviewer were run on this branch; findings (dead schema path, `@Database` paren parsing, db_version enforcement, unchecked revert, build-file patching, symlinks, memory-file poisoning, secret scope, unwrapped feedback) were fixed with tests. Tests pass on Python 3.13 and 3.12.
