"""Guard: importing embeddings must silence the benign urllib3 LibreSSL warning.

On macOS system Python (LibreSSL), every search.py invocation otherwise prints
a urllib3 NotOpenSSLWarning to stderr before results, polluting hook output and
captured search results. embeddings.py registers a process-wide warnings filter
at import; search.py imports embeddings at module load, so both entrypoints are
covered. This test keeps that filter from regressing.
"""

from __future__ import annotations

import subprocess
import sys

from tests.conftest import REPO_ROOT


def test_urllib3_libressl_warning_is_filtered():
    # Reproduce real runtime (hooks invoke search.py as a subprocess): a fresh
    # interpreter that imports embeddings then re-emits the urllib3 LibreSSL
    # warning must produce no stderr. A subprocess avoids pytest's per-test
    # warnings plugin, which would otherwise reset the filter list.
    code = (
        "import sys; sys.path.insert(0, r'{tools}');"
        "import embeddings, warnings;"
        'warnings.warn("urllib3 v2 only supports OpenSSL 1.1.1+, currently '
        "the 'ssl' module is compiled with 'LibreSSL 2.8.3'.\", Warning)"
    ).format(tools=REPO_ROOT / ".claude" / "tools")
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == "", result.stderr
