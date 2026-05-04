# Contributing to less_tokens

Thanks for taking the time to contribute.

## Ways to contribute

- **Bug reports** — open an Issue using the Bug Report template
- **Feature requests** — open an Issue using the Feature Request template
- **Code** — fork, branch, and open a Pull Request

## Before you start

- Check [open issues](../../issues) to avoid duplicating work.
- For significant changes, open an Issue first to discuss the approach.

## Development setup

```bash
git clone https://github.com/hofmockel/less_tokens_claude.git
cd less_tokens_claude
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install fastembed numpy
```

## Submitting a Pull Request

1. Fork the repo and create a branch from `main`:
   ```bash
   git checkout -b fix/short-description
   ```
2. Make focused, atomic commits with clear imperative messages.
3. Test your changes manually (see [README.md](README.md) for verification steps).
4. Open a PR against `main` with a description of what changed and why.

## Commit message style

Use the imperative mood and keep the subject line under 72 characters:

```
Add chunking support for TOML files
Fix VENV_PY resolution on Windows ARM
Remove deprecated --no-cache flag
```

## Reporting security issues

Do **not** open a public Issue for security vulnerabilities. See [SECURITY.md](SECURITY.md).
