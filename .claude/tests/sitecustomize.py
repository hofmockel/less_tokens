"""Enable coverage collection in subprocesses during coverage runs."""
from __future__ import annotations

import os

if os.environ.get("COVERAGE_PROCESS_START"):
    try:
        import coverage
    except ImportError:
        pass
    else:
        coverage.process_startup()
