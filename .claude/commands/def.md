Locate a symbol's definition by exact `file:line` — cheaper than grepping.

```bash
.claude/.venv-tokens/bin/python .claude/tools/symbols.py "$ARGUMENTS"
```

Use the printed `Read(offset=…, limit=…)` to read only the definition, not the
whole file. For usages (not the definition) or a fuzzy match, use `/search`.

If nothing is found, refresh the symbol index:

```bash
.claude/.venv-tokens/bin/python .claude/tools/symbols.py refresh
```
