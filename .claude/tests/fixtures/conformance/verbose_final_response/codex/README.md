# `verbose_final_response` — Codex bounded live capture

Captured 2026-07-22 against the installed `0.144.6`-contract adapter. `.codex/hooks/terse-reminder.py`
invoked directly with real stdin `Stop` payloads (`stop-verbose.json` / `stop-terse.json`), same
verbose/terse pair used for the Claude-side capture in this workload.

## Method / key parity finding

Unlike Claude's `caveman-reminder.py`, which reads the response text out of a transcript file
via `transcript_path`, Codex's `terse-reminder.py` reads `payload["response"]` directly — no
transcript file involved. This is a real mechanism difference, not just an adapter detail: a
Codex host that omits `response` from the `Stop` payload silently no-ops this hook (falls through
`if not isinstance(response, str): return 0`), whereas Claude's transcript-read path degrades to
an empty string on the same kind of gap but the read path itself is still exercised.

## Results

| Probe | Output | Exit |
| --- | --- | --- |
| Verbose (654 chars / 119 words, 5 filler phrases) | `Response budget exceeded. Keep response concise. No filler. filler phrases detected: feel free to, i hope this helps, in conclusion, please let me know if, to summarize` | 2 |
| Terse (78 chars / 13 words, 0 filler phrases) | (no output) | 0 |

Same 576-char (88%) reduction as the Claude-side capture, confirming the shared `response_budget.analyze`
logic behaves identically once each adapter has extracted the response text. `event_fired: true`,
`action_enforced: true`, `basis: measured` for `verbose_final_response:codex:0.144.6`.
