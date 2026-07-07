"""SQLite/parquet database layer. Local files only, rebuilt by one command.
Author: Avia Solutions.
"""
from __future__ import annotations
from pathlib import Path
import sqlite3

SCHEMA = Path(__file__).resolve().parent / "schema.sql"


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    with open(SCHEMA, "r", encoding="utf-8") as fh:
        conn.executescript(fh.read())
    conn.commit()
