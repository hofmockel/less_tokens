Run a vector search over the less_tokens index and show the top results.

```bash
.claude/.venv-tokens/bin/python .claude/tools/search.py "$ARGUMENTS"
```

If the command errors or returns no results, check whether the index exists:

```bash
.claude/.venv-tokens/bin/python .claude/tools/embeddings.py stats
```

If the index is empty or missing, build it:

```bash
.claude/.venv-tokens/bin/python .claude/tools/embeddings.py refresh
```
