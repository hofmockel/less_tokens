#!/usr/bin/env python3
"""Native git pre-push hook: block a push whose continue.md is stale.

Installed by install.py into `.git/hooks/pre-push` (or the repo's configured
hooksPath). Git changes cwd to the working tree root before invoking any
hook, so Path.cwd() is reliably the repo root here.

Git feeds ref updates on stdin as `<local ref> <local sha1> <remote ref>
<remote sha1>` lines; we check continue.md as committed at each non-deleted
local sha1, since that's what would actually land on the remote.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path.cwd()
# Mirrors continue-freshness.py's dual-location import: this script runs
# unmodified from agents/common/hooks/ in the less_tokens source repo itself,
# but install.py only ever copies it flat into .claude/hooks/common/ or
# .less_tokens/hooks/ on a real target — there's no agents/ package there.
sys.path[:0] = [
    str(REPO),
    str(REPO / "agents" / "common" / "hooks"),
    str(REPO / ".claude" / "hooks" / "common"),
    str(REPO / ".less_tokens" / "hooks"),
]

try:
    from agents.common.hooks.continue_freshness import check_continue_freshness_at_ref  # type: ignore[import]
except Exception:
    try:
        from continue_freshness import check_continue_freshness_at_ref  # type: ignore[no-redef]
    except Exception:
        sys.exit(0)  # fail open: a broken import must never block a push

ZERO_SHA = "0" * 40


def main() -> int:
    try:
        lines = sys.stdin.read().splitlines()
    except Exception:
        return 0

    for line in lines:
        parts = line.split()
        if len(parts) != 4:
            continue
        _local_ref, local_sha1, _remote_ref, _remote_sha1 = parts
        if local_sha1 == ZERO_SHA:
            continue  # branch deletion, nothing to check
        try:
            code, _, stderr = check_continue_freshness_at_ref(REPO, local_sha1)
        except Exception:
            continue  # fail open on any unexpected error
        if code == 2:
            print("Continue-freshness: " + stderr, file=sys.stderr)
            print(
                "\nRegenerate continue.md with the /continue skill, then push again.\n"
                "To push anyway without updating it: git push --no-verify",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
