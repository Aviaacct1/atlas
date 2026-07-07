"""Repo validity gate (run by the pre-commit hook). Author: Avia Solutions.

Fails with exit 1 if either of the two failure classes we have actually hit is present:
  1. a served JSON under webapp/data is not valid JSON (the truncation incidents), or
  2. a Python file hard-codes an absolute sandbox session path (the unrunnable-on-John's-machine bug).
The path resolver (avia_forecast/paths.py) is exempt because its sandbox path is a documented fallback.
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAD_PATH = re.compile(r"/sessions/[a-z0-9-]+/mnt/")
errs = []

for f in glob.glob(os.path.join(ROOT, "webapp", "data", "*.json")):
    try:
        with open(f, encoding="utf-8") as fh:
            json.load(fh)
    except Exception as e:
        errs.append(f"invalid JSON: {os.path.relpath(f, ROOT)}: {e}")

for f in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True):
    if os.path.basename(f) == "paths.py" or "__pycache__" in f:
        continue
    for i, line in enumerate(open(f, encoding="utf-8", errors="replace"), 1):
        if BAD_PATH.search(line):
            errs.append(f"absolute sandbox path: {os.path.relpath(f, ROOT)}:{i}")

if errs:
    print("VALIDATION FAILED (" + str(len(errs)) + "):")
    for e in errs:
        print("  - " + e)
    sys.exit(1)
print("validation OK: served JSON valid; no absolute sandbox paths")
