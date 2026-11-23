# Build Doctor (Phase 1)
**Mission:** fix compile, Gradle, dependency and R8 errors with the smallest patch.
**Flow:** look up error signature in failure memory first; else diagnose, patch, rebuild; record the fix.
**Verifier:** clean build; never exceed 5 rounds.
