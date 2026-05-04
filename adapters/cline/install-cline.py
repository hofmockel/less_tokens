#!/usr/bin/env python3
"""Cline adapter installer.

Run from your project root after the base installer:
    python3 path/to/less_tokens_claude/install.py
    python3 path/to/less_tokens_claude/adapters/cline/install-cline.py [--venv PATH]

What it does:
  1. Copies adapters/cline/clinerules/* into <project>/.clinerules/
  2. Sets STATE_DIR in tools/search_config.py to .less_tokens/state/
     (so Cline projects don't get a stray .claude/ directory)
  3. Installs the `mcp` SDK into the project venv
  4. Prints the JSON snippet to merge into cline_mcp_settings.json
     (location varies by OS; printed for reference) and the OS-specific path

Hooks: Cline's hook system has the same shape as Claude Code's (PreToolUse,
PostToolUse, PreCompact, etc.). The existing hooks/*.py files should work
directly once Cline's exact hook config schema is confirmed — see README.md
for the verification probe.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ADAPTER = Path(__file__).resolve().parent
SOURCE = ADAPTER.parent.parent
TARGET_ROOT = Path.cwd().resolve()


def venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def detect_venv() -> Path | None:
    for candidate in [".venv", "venv", "env", "app/.venv"]:
        d = TARGET_ROOT / candidate
        if venv_python(d).exists():
            return d
    return None


def copy_clinerules(force: bool) -> int:
    src = ADAPTER / "clinerules"
    dst = TARGET_ROOT / ".clinerules"
    dst.mkdir(parents=True, exist_ok=True)
    copied = skipped = 0
    for f in sorted(src.glob("*.md")):
        target = dst / f.name
        if target.exists() and not force:
            print(f"  ! skip (exists): {target.relative_to(TARGET_ROOT)}")
            skipped += 1
            continue
        shutil.copy2(f, target)
        print(f"  + {target.relative_to(TARGET_ROOT)}")
        copied += 1
    print(f"  .clinerules/: {copied} copied, {skipped} skipped")
    return copied


def patch_state_dir() -> None:
    cfg = TARGET_ROOT / "tools" / "search_config.py"
    if not cfg.exists():
        print("  WARN: tools/search_config.py not found — run base install.py first",
              file=sys.stderr)
        return
    text = cfg.read_text(encoding="utf-8")
    if 'BASE / ".less_tokens" / "state"' in text:
        print("  STATE_DIR already set to .less_tokens/state/")
        return
    new = text.replace(
        'STATE_DIR: Path = BASE / ".claude" / "state"',
        'STATE_DIR: Path = BASE / ".less_tokens" / "state"',
    )
    if new == text:
        print("  WARN: could not patch STATE_DIR (template line not found)",
              file=sys.stderr)
        return
    cfg.write_text(new, encoding="utf-8")
    print("  STATE_DIR -> .less_tokens/state/")


def install_mcp(venv_py: Path) -> int:
    print(f"\nInstalling `mcp` into {venv_py}...")
    try:
        subprocess.check_call(
            [str(venv_py), "-m", "pip", "install", "--quiet", "mcp"]
        )
        print("  OK")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"  pip install failed (exit {e.returncode})", file=sys.stderr)
        return 1


SETTINGS_PATHS = {
    "darwin": "~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
    "linux": "~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
    "win32": "%APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venv", type=Path,
                    help="path to virtualenv (auto-detected if omitted)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite existing .clinerules/* files")
    ap.add_argument("--skip-deps", action="store_true",
                    help="skip pip install of mcp")
    args = ap.parse_args()

    print(f"Installing Cline adapter into {TARGET_ROOT}")
    print(f"Adapter source: {ADAPTER}\n")

    print("[1/4] Copying .clinerules/...")
    copy_clinerules(args.force)

    print("\n[2/4] Patching tools/search_config.py STATE_DIR...")
    patch_state_dir()

    venv_dir = args.venv or detect_venv()
    if venv_dir is None:
        print("\n[3/4] WARN: no venv detected; skipping pip install. "
              "Pass --venv PATH or run install.py first.", file=sys.stderr)
        venv_py = Path("python3")
    else:
        venv_py = venv_python(venv_dir)
        if not args.skip_deps:
            print(f"\n[3/4] Installing `mcp` into {venv_dir}...")
            if install_mcp(venv_py) != 0:
                return 1
        else:
            print("\n[3/4] Skipping pip install (--skip-deps).")

    server_path = ADAPTER / "mcp-search" / "server.py"

    print("\n[4/4] Done.")
    print("\n" + "="*60)
    print("NEXT STEPS — register the MCP server with Cline")
    print("="*60)

    settings_path = SETTINGS_PATHS.get(sys.platform, SETTINGS_PATHS["linux"])
    print(f"\nMerge this entry into cline_mcp_settings.json:\n  {settings_path}")
    print()
    print("    {")
    print('      "mcpServers": {')
    print('        "less-tokens-search": {')
    print(f'          "command": "{venv_py}",')
    print(f'          "args": ["{server_path}"],')
    print('          "alwaysAllow": ["search"],')
    print('          "disabled": false')
    print('        }')
    print('      }')
    print('    }')
    print()
    print("Restart Cline (reload VS Code window) for it to pick up the new server.")
    print()
    print("Hooks: Cline supports PreToolUse/PostToolUse/PreCompact hooks with the")
    print("same JSON-on-stdin shape as Claude Code. To wire the existing hooks for")
    print("Strategies 1, 3, and 5, follow the verification probe in adapters/cline/README.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
