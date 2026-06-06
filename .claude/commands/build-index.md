Build or refresh the less_tokens vector index.

```bash
.claude/.venv-tokens/bin/python .claude/tools/embeddings.py refresh
```

After building, verify coverage:

```bash
.claude/.venv-tokens/bin/python .claude/tools/embeddings.py health
```

If the venv does not exist yet, create it first:

```bash
python3 -m venv .claude/.venv-tokens
.claude/.venv-tokens/bin/pip install fastembed numpy --quiet
```
