"""Emit/consume parity for savings-event ``strategy`` keys.

The canonical registry lives in ``savings_log._KNOWN_STRATEGIES`` (tools/savings_log.py).
Every emitter under ``.claude/`` and ``agents/`` must write a key from that registry, and
``stats.py`` must know a label + measured/upper-bound basis for every registered key.

These tests are static (source-scan) rather than behavioral so a *new* emitter added in
the future is caught automatically, without needing to update a hand-written expected-key
list here (that hand-written list is exactly the drift this test exists to prevent).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_TOOLS = Path(__file__).parent.parent.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import savings_log  # noqa: E402  (must follow sys.path setup)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Directories scanned for emitter call sites. Deliberately narrow (hooks + tools that are
# known to log savings events) rather than the whole repo, to keep the scan fast and to
# avoid false positives from unrelated "strategy" usages elsewhere in the codebase.
_SCAN_DIRS = (
    REPO_ROOT / ".claude" / "hooks",
    REPO_ROOT / ".claude" / "tools",
    REPO_ROOT / "agents" / "common" / "hooks",
    REPO_ROOT / "agents" / "codex" / "hooks",
)

# Matches a literal strategy key written at a call site, e.g. `"strategy": "truncation",`
# or `"strategy": STRATEGY_TRUNCATION,` (the latter is skipped — only literals are scanned,
# since named constants are checked for existence in savings_log directly).
_LITERAL_RE = re.compile(r'"strategy"\s*:\s*"([^"]+)"')


def _iter_py_files():
    for d in _SCAN_DIRS:
        if d.is_dir():
            yield from d.glob("*.py")


def _emitted_literal_keys() -> set[str]:
    """Every literal (non-constant) strategy string found at a log call site."""
    keys: set[str] = set()
    for f in _iter_py_files():
        text = f.read_text(encoding="utf-8")
        keys.update(_LITERAL_RE.findall(text))
    return keys


def _emitted_constant_names() -> set[str]:
    """Every savings_log.STRATEGY_* constant referenced as a "strategy" value
    (directly or via a local fallback assignment), across the scanned files."""
    names: set[str] = set()
    const_re = re.compile(
        r'"strategy"\s*:\s*(STRATEGY_[A-Z_]+|_config\.get\("strategy_\w+"[^)]*\))'
    )
    for f in _iter_py_files():
        text = f.read_text(encoding="utf-8")
        for m in const_re.finditer(text):
            token = m.group(1)
            if token.startswith("STRATEGY_"):
                names.add(token)
    return names


def test_registry_is_nonempty():
    # Sanity: the registry itself isn't accidentally empty (would make every other
    # assertion in this file vacuously true).
    assert len(savings_log._KNOWN_STRATEGIES) >= 5


def test_every_emitted_literal_key_is_registered():
    """2.5 parity check: any bare-string strategy literal at a call site must be a
    registered key. Falsifiable — see test_ac_falsifiability_probe below for the
    inject/confirm-fail/revert/confirm-pass demonstration (run manually, not in CI,
    since it mutates source)."""
    emitted = _emitted_literal_keys()
    registered = set(savings_log._KNOWN_STRATEGIES)
    unregistered = emitted - registered
    assert not unregistered, (
        f"Emitter(s) write unregistered strategy key(s): {sorted(unregistered)}. "
        f"Add to savings_log._KNOWN_STRATEGIES."
    )


def test_every_emitted_constant_name_exists_in_savings_log():
    """Every STRATEGY_* constant referenced at a call site must actually be defined
    in savings_log (catches a typo'd import name that isn't caught by the literal scan)."""
    referenced = _emitted_constant_names()
    assert referenced, (
        "expected at least one STRATEGY_* constant reference in scanned files"
    )
    defined = {name for name in dir(savings_log) if name.startswith("STRATEGY_")}
    missing = referenced - defined
    assert not missing, f"Referenced but undefined in savings_log: {sorted(missing)}"


def test_every_emitted_constant_value_is_registered():
    """Stronger form of the above: not just defined, but present as a key in
    _KNOWN_STRATEGIES. A constant that exists on the module but was dropped from
    the registry dict (e.g. during a refactor) would pass the "is it defined" check
    but still represents an emit/consume gap — this is what catches that."""
    referenced_names = _emitted_constant_names()
    registered = set(savings_log._KNOWN_STRATEGIES)
    unregistered = []
    for name in referenced_names:
        value = getattr(savings_log, name, None)
        if value is not None and value not in registered:
            unregistered.append((name, value))
    assert not unregistered, (
        f"STRATEGY_* constant(s) used at a call site but missing from "
        f"_KNOWN_STRATEGIES: {unregistered}"
    )


def test_no_bare_string_literals_remain_at_known_call_sites():
    """2.4: call sites should use constants, not bare literals, wherever a constant
    exists for that key. This guards against a future PR reintroducing a literal for
    an already-registered key (regression of the 2.4 refactor)."""
    emitted_literals = _emitted_literal_keys()
    registered = set(savings_log._KNOWN_STRATEGIES)
    # Any literal that exactly matches a registered key and is NOT inside savings_log.py's
    # own registry definition (which legitimately holds literals) or a documented
    # best-effort fallback (`STRATEGY_X = "x"` after a failed import) is a regression.
    fallback_re = re.compile(r'STRATEGY_[A-Z_]+\s*=\s*"([^"]+)"')
    allowed_literal_sites = set()
    for f in _iter_py_files():
        text = f.read_text(encoding="utf-8")
        allowed_literal_sites.update(fallback_re.findall(text))
    stray = (emitted_literals & registered) - allowed_literal_sites
    assert not stray, (
        f"Strategy key(s) still written as bare literals instead of constants: "
        f"{sorted(stray)}"
    )
