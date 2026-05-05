# Contributing to less_tokens

Thanks for taking the time to contribute.

## Workflow

All contributions — bug reports, feature requests, and fixes — go through Pull Requests. Discussion happens in PR comments on GitHub.

There are three valid PR types:

| PR type | What it contains |
|---|---|
| **Backlog-only** | Adds an entry to BACKLOG.md (reports a bug or proposes a feature); no code change required |
| **Fix-only** | Implements a fix or feature; code changes only |
| **Combined** | Adds a backlog entry and implements it in the same PR; code changes only |

The maintainer handles CHANGELOG entries and BACKLOG deletions before merging.

## Reporting a bug or proposing a feature

1. Fork the repo.
2. Edit [BACKLOG.md](BACKLOG.md): add your entry to `## Bugs` (for bugs) or the appropriate feature section. For bugs, include a file:line reference and a clear What/Why/Fix description.
3. Open a PR against `main`. Explain your reasoning in the PR description — that's where the discussion happens.

## Fixing something

1. Fork the repo and create a branch from `main`:
   ```bash
   git checkout -b fix/short-description
   ```
2. Make your change.
3. Test manually: install into a scratch project, verify search returns results, confirm hooks fire.
4. Open a PR against `main`.

The maintainer will handle the CHANGELOG entry and BACKLOG deletion before merging.

## Commit message style

Use the imperative mood, subject line under 72 characters:

```
Add chunking support for TOML files
Fix VENV_PY resolution on Windows ARM
Remove deprecated --no-cache flag
```

## Development setup

```bash
git clone https://github.com/hofmockel/less_tokens_claude.git
cd less_tokens_claude
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install fastembed numpy
```

## Security

Do **not** add security vulnerabilities to BACKLOG.md or any public file. See [SECURITY.md](SECURITY.md).
