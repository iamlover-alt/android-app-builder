# ADR 0001: Typed artifact handoffs, no agent-to-agent chat
Date: 2026-11-22
Status: accepted

## Context
Multi-agent failures cluster in design, inter-agent misalignment and weak verification (MAST taxonomy). Chat-based handoffs lose detail.

## Decision
Agents communicate only through schema-validated artifacts in the Project Graph (`schemas/`). The Orchestrator starts an agent when all its inputs exist.

## Measured effect
Not yet measured; baseline benchmark run pending.

## Consequences
Malformed handoffs fail fast. Every new handoff needs a schema.
