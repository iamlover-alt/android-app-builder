# Failure log

One row per escalation or benchmark failure. Review monthly: which verifier was missing?

| Date | Benchmark app | Agent | MAST category (design / misalignment / verification) | What happened | Fix or ADR |
| --- | --- | --- | --- | --- | --- |
| 2026-11-23 | n/a (Day 1 build) | builder-lead | verification | critic-reviewer and security-reviewer were not run on branch day-1 (unattended scheduled session). Orchestrator verified only by 12 offline unit tests with fake agents. | Run both reviews at the start of Day 2 |
| 2026-11-25 | n/a (Day 3 build) | agent-engineer | verification | Reviews caught `wrap_untrusted` single-pass strip (nested `</untrusted>` payload escaped the data block) and an unvalidated API URL that would carry the key; the first test only covered the plain case. | Loop/regex strip, https-only URL, no redirects, bypass tests |
| 2026-11-26 | n/a (Day 4 build) | agent-engineer | verification | Reviews found the Room schema allowance was dead code, `@Database` parsing stopped at the first `)` (exportSchema=false bypass), Build Doctor could patch Gradle scripts, and memory entries/symlinks were trusted. My first tests covered only the happy paths. | Balanced-paren parser, db_version check, source-only patch paths, symlink and memory-load validation, tests |
