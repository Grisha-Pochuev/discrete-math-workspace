#!/usr/bin/env python3
"""Readable chunk loader for the adaptive Second approach 2.0 implementation."""
from pathlib import Path

_parts = sorted((Path(__file__).with_name("adaptive_parts")).glob("part-*.inc"))
if not _parts:
    raise RuntimeError("adaptive Second approach 2.0 source chunks are missing")
_source = "".join(path.read_text(encoding="utf-8") for path in _parts)
exec(compile(_source, str(Path(__file__).with_name("adaptive_v2.generated.py")), "exec"), globals())
