"""outputs/run_id - deterministic run-id content hash (O-21, Development Guide C4). Author: Avia Solutions.

A run is identified by a content hash over the code version, the applied override pack and the data
snapshot ids. Same inputs -> same id, so a number a client quotes back is reproducible on demand; any
change to code, pack or data -> a different id. The adjustment ledger binds to the run id so it is
always clear which run an adjustment set was taken against.
"""
from __future__ import annotations
import hashlib
import json

CODE_VERSION = "method-spec-0.2"


def run_id(code_version: str, pack: dict, data_snapshot_ids: dict) -> str:
    payload = json.dumps({"code": code_version, "pack": pack or {}, "data": data_snapshot_ids or {}},
                         sort_keys=True, default=str)
    return "r" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def bind_ledger(ledger: dict, rid: str) -> dict:
    out = dict(ledger)
    out["run_id"] = rid
    return out
