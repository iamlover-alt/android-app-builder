# Phase 1 build plan: core loop

Goal: idea in, single-module app out that builds and passes its own tests.

Order:
1. Schemas (`schemas/`): done.
2. Agent specs (`agents/`): done.
3. Orchestrator runtime: task DAG executor with artifact-ready triggers and the 5-round cap.
4. Sandbox image: JDK 17+, Android SDK (API 36), warm Gradle daemon.
5. Tool wrappers: edit-then-lint, gradle-run, emulator-run.
6. Benchmark: 10 specs first (to-do, habit tracker, notes, timer, unit converter, ...), metrics: first-green-build rate, acceptance pass rate.

Open decisions: orchestrator language and host; model routing per agent; where the sandbox runs.
