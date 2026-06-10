#!/usr/bin/env python3
"""check_design_tokens.py - assert the shared design-token block is identical
in the framework brain view and the a_bgt_rsi consumer UI.

Each tokens.css carries a marker-fenced block:

    /* ====== BEGIN SHARED TOKENS ... */
    ...shared custom properties...
    /* ====== END SHARED TOKENS ... */

The text between the markers must stay identical (whitespace-insensitive)
across the two copies; everything outside the markers is per-project and free
to drift. The framework default resolves relative to this script's repo (so it
works from a worktree or from main); the consumer path is fixed. Read-only.

Usage: check_design_tokens.py [FRAMEWORK_CSS CONSUMER_CSS]

Exit 0 blocks identical, 1 blocks differ (unified diff printed),
2 a file or its marker pair is missing.
"""
from __future__ import annotations

import difflib
import sys
from pathlib import Path

BEGIN = "====== BEGIN SHARED TOKENS"
END = "====== END SHARED TOKENS"

REPO = Path(__file__).resolve().parent.parent
DEFAULTS = (
    REPO / "memory" / "brain" / "view" / "tokens.css",
    Path("/home/decross1/projects/a_bgt_rsi/ui/frontend/src/tokens.css"),
)


def shared_block(path):
    """Whitespace-normalized lines between the markers, or None + stderr."""
    if not path.is_file():
        print("ERROR: tokens file missing: %s" % path, file=sys.stderr)
        return None
    text = path.read_text(encoding="utf-8")
    b, e = text.find(BEGIN), text.find(END)
    if b == -1 or e == -1 or e < b:
        print("ERROR: %s: marker pair not found (need %r before %r)"
              % (path, BEGIN, END), file=sys.stderr)
        return None
    # Between markers: after the BEGIN marker's line, before the END line.
    start = text.index("\n", b) + 1
    end = text.rfind("\n", 0, e) + 1
    lines = [" ".join(ln.split()) for ln in text[start:end].splitlines()]
    return [ln for ln in lines if ln]


def main(argv):
    if len(argv) not in (0, 2):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    fw, consumer = (Path(argv[0]), Path(argv[1])) if argv else DEFAULTS
    a, b = shared_block(fw), shared_block(consumer)
    if a is None or b is None:
        return 2
    if a == b:
        print("OK: shared token block identical (%d lines)\n  %s\n  %s"
              % (len(a), fw, consumer))
        return 0
    diff = difflib.unified_diff(a, b, fromfile=str(fw), tofile=str(consumer),
                                lineterm="")
    print("FAIL: shared token blocks differ (whitespace-normalized):")
    for line in diff:
        print(line)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
