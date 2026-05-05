# Bug-Hunt Log

One entry per completed hunt round. Append after each run; never edit past entries.

See [bughunt.md](bughunt.md) for the protocol, severity rubric, stop rule, and agent prompt template.

---

## Round template

```
## Round N — YYYY-MM-DD

**Bugs surfaced:** N
**Severity breakdown:** N data-loss / N silent / N ux / N cosmetic
**Median severity:** X
**Overlap with prior rounds:** N/N (N%)
**New files hit:** file1.py, file2.py
**Cumulative file coverage:** N/N target files (N%)

**Stop rule signals:**
- Severity slide: pass/fail
- Overlap rate ≥ 60%: pass/fail
- File coverage ≥ 80%: pass/fail

**Decision:** run another round / stop and fix
```

---
