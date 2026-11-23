# Project rules

Android App Builder: a multi-agent system that turns an idea into a signed, tested, store-ready native Android app. Start with docs/week-plan.md and docs/phase-1-build-plan.md.

- Specialist agents live in .claude/agents/. Start with builder-lead; every branch is reviewed by critic-reviewer, and by security-reviewer when it touches secrets, subprocesses, network or dependencies.
- Python 3.12 for the builder (ADR 0002); generated apps are Kotlin and Compose, target API 36 or higher.
- Agents exchange schema-validated artifacts (schemas/), never free chat.
- Secrets (ANTHROPIC_API_KEY, signing keys, Play credentials) never go into files, prompts, logs or fixtures.
- Tests run offline with fakes. Never claim emulator or Play verification that did not happen; record gaps in docs/week-plan.md.
- Release to production always needs a human approval.
- Commit messages end with: Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
