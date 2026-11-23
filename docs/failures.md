# Failure log

One row per escalation or benchmark failure. Review monthly: which verifier was missing?

| Date | Benchmark app | Agent | MAST category (design / misalignment / verification) | What happened | Fix or ADR |
| --- | --- | --- | --- | --- | --- |
| 2026-11-23 | n/a (Day 1 build) | builder-lead | verification | critic-reviewer and security-reviewer were not run on branch day-1 (unattended scheduled session). Orchestrator verified only by 12 offline unit tests with fake agents. | Run both reviews at the start of Day 2 |
