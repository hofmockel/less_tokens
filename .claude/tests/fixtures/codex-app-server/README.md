# Codex app-server fixtures

Sanitized, content-free results from bounded live probes of the experimental
Codex app-server protocol. These fixtures record protocol shape and numeric
measurements only; prompts, summaries, transcript bodies, and credentials are
not retained.

`0.144.6/thread-compact-start.json` was captured with a fresh synthetic thread
whose working directory was an empty temporary directory. The client called
`thread/compact/start` after one completed turn and observed a completed
`contextCompaction` item. Token counts come from the rollout's two ordered
`token_count` events. Transcript byte counts demonstrate that rollout JSONL is
append-only and must not be used as a savings measure.

Re-capture on each newly supported Codex release before changing the verdict.
Stop after one completed compaction. Do not use a repository working directory
or real task content.
