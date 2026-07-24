# Contributing

Fork, add an entry to [BACKLOG.md](BACKLOG.md), and open a PR.

- Check [DECISIONS.md](DECISIONS.md) first — a proposal already rejected there needs new
  evidence, not a repeat pitch.
- Code-changing PRs need a `CHANGELOG.md` `[Unreleased]` entry citing the backlog ID
  (`[P2] ...`), and must delete the shipped item's row from `BACKLOG.md` (no strike-through,
  no "DONE" marker) — see `CLAUDE.md` → *Backlog and changelog lifecycle*.
- Run `.claude/tools/dev.py unit` (and `integration` for install/hook-wiring changes) before
  opening the PR; CI runs the same suite plus the doc-consistency gates in
  `.pre-commit-config.yaml`.

## License

By contributing, you agree your contribution is licensed under this repo's [MIT license](LICENSE).
