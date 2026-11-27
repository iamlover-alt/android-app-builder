# Benchmark

Ten starter specs (grow toward 50). Every design change is judged by running these and appending to each spec's run record.

Metrics: first-green-build rate, acceptance pass rate, crash-free sessions, human interventions per app, cost and wall-clock per app.

Rule: a change that lowers pass rate or raises interventions needs an ADR explaining the trade.

## Running
`python benchmark/run.py --specs 01-05` runs the pipeline (`appbuilder/pipeline.py`) on each spec and appends one row to its run record. The model is real if `ANTHROPIC_API_KEY` is set, otherwise the fake model; tools are fake Gradle (`--tools real` is not available yet). `--no-record` runs without editing specs; per-run JSON goes to `runs/benchmark/` (gitignored).

Reading a row: `n/a` means it was not measured (fake Gradle compiles nothing and executes no tests). A row marked FAKE model checks wiring only, never model quality. Do not compare FAKE rows with real ones.
