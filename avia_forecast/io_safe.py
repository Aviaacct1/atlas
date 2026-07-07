"""Atomic JSON writes with a parse-back check. Author: Avia Solutions.

A front end must never be served a half-written file. This writes to a temp file in the SAME
directory, flushes and fsyncs, parses it back to prove it is valid JSON, then os.replace()s it
into place (atomic on one filesystem). If anything fails the temp file is removed and the existing
good file is left untouched, so an interrupted build cannot truncate the served data.
"""
import json
import os
import tempfile


def dump_atomic(obj, path, indent=None):
    """Drop-in for json.dump(obj, open(path, "w")): write obj to path atomically, verified."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        with open(tmp, encoding="utf-8") as f:      # parse-back: refuse to publish invalid JSON
            json.load(f)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
