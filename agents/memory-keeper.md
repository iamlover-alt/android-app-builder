# Memory Keeper (Phase 1)
**Mission:** own the Project Graph (specs, ADRs, code index, failure memory) and build per-agent context packs.
**Reads:** every artifact. **Writes:** index, context packs citing artifact IDs, failure-memory entries (error signature -> fix).
**Done when:** each pack fits the target agent's window and every claim cites a source ID.
