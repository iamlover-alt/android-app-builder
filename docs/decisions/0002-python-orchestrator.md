# ADR 0002: Python orchestrator, Anthropic API for agents
Date: 2026-11-22
Status: accepted

## Context
Phase 1 needs a task-DAG executor, schema validation and subprocess control (Gradle, ADB). The generated apps are Kotlin; the builder itself does not have to be.

## Decision
Orchestrator, tools and CLI in Python 3.12 (`jsonschema`, `pytest`). Agents call the Anthropic API with their spec in `agents/` as the system prompt. Sandbox runs in a container. Model routing: strongest model for Orchestrator, Architect and critics; faster model for bulk code and tests. Default host: local CLI plus container; hosted service deferred.

## Measured effect
Not yet measured.

## Consequences
Fast iteration and good subprocess tooling. Revisit hosting after v0.1 benchmark.
