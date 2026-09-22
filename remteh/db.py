"""Работа с базой данных SQLite: схема, подключение, транзакции."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name   TEXT NOT NULL,
    phone       TEXT NOT NULL,
    email       TEXT NOT NULL DEFAULT '',
    address     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS equipment (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    kind        TEXT NOT NULL,
    brand       TEXT NOT NULL,
    model       TEXT NOT NULL,
    serial      TEXT NOT NULL UNIQUE,
    notes       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS masters (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       TEXT NOT NULL,
    specialization  TEXT NOT NULL,
    phone           TEXT NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    number       TEXT NOT NULL UNIQUE,
    client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE RESTRICT,
    master_id    INTEGER REFERENCES masters(id) ON DELETE SET NULL,
    description  TEXT NOT NULL,
    status       TEXT NOT NULL,
    priority     TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    planned_date TEXT,
    completed_at TEXT,
    cost         REAL NOT NULL DEFAULT 0,
    notes        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS works (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    hours      REAL NOT NULL CHECK (hours > 0),
    price      REAL NOT NULL CHECK (price >= 0)
);

CREATE TABLE IF NOT EXISTS status_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    old_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    comment    TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_equipment_client ON equipment(client_id);
CREATE INDEX IF NOT EXISTS idx_requests_client ON requests(client_id);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_requests_master ON requests(master_id);
CREATE INDEX IF NOT EXISTS idx_works_request ON works(request_id);
CREATE INDEX IF NOT EXISTS idx_history_request ON status_history(request_id);
"""


class Database:
    """Тонкая обёртка над sqlite3 с единой схемой и управлением транзакциями."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        self.close()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.connection.execute(sql, params)

    def executemany(self, sql: str, rows: list[tuple]) -> sqlite3.Cursor:
        return self.connection.executemany(sql, rows)

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()
