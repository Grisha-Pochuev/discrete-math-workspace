#!/usr/bin/env python3
"""Compatibility entrypoint for the adaptive Second approach 2.0 collector.

The collector only reads JSON/gzip artifacts and does not perform numerical
optimization.  Historical failed-job reruns may execute it in a clean Python
environment where NumPy is not installed, so provide a harmless import stub in
that narrow case.  Production runners and smoke tests still use real NumPy.
"""
from __future__ import annotations

import sys
import types

try:
    import numpy  # noqa: F401
except ModuleNotFoundError:
    sys.modules["numpy"] = types.ModuleType("numpy")

from adaptive_v2 import collect_main

if __name__ == "__main__":
    raise SystemExit(collect_main())
