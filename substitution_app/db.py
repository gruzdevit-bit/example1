"""Хранилище сервиса «Замещение» на SQLite."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS substitutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    role_id INTEGER NOT NULL REFERENCES roles(id),
    deputy_id INTEGER NOT NULL REFERENCES users(id),
    date_from TEXT NOT NULL,
    date_to TEXT NOT NULL,
    revoked_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_substitutions_owner ON substitutions(owner_id);
CREATE INDEX IF NOT EXISTS idx_substitutions_deputy ON substitutions(deputy_id);
CREATE INDEX IF NOT EXISTS idx_substitutions_role ON substitutions(role_id);
"""

SEED_ROLES = [
    ("Р1", "Первая роль"),
    ("Р2", "Вторая роль"),
    ("Р3", "Третья роль"),
]

SEED_USERS = [
    ("Пользователь А", "a@example.com"),
    ("Пользователь Б", "b@example.com"),
    ("Пользователь В", "v@example.com"),
    ("Пользователь Г", "g@example.com"),
    ("Пользователь Д", "d@example.com"),
]


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        _seed(conn)
        conn.commit()
    finally:
        conn.close()


def _seed(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        return

    conn.executemany("INSERT INTO roles (name, description) VALUES (?, ?)", SEED_ROLES)
    conn.executemany("INSERT INTO users (full_name, email) VALUES (?, ?)", SEED_USERS)

    owner_id = conn.execute(
        "SELECT id FROM users WHERE full_name = ?", ("Пользователь А",)
    ).fetchone()[0]
    role_ids = [row[0] for row in conn.execute("SELECT id FROM roles ORDER BY id").fetchall()]
    conn.executemany(
        "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)",
        [(owner_id, role_id) for role_id in role_ids],
    )


def get_user(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def list_users(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM users ORDER BY id").fetchall()


def list_roles(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM roles ORDER BY id").fetchall()


def user_roles(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT r.*
        FROM roles r
        JOIN user_roles ur ON ur.role_id = r.id
        WHERE ur.user_id = ?
        ORDER BY r.id
        """,
        (user_id,),
    ).fetchall()


def users_with_roles(conn: sqlite3.Connection) -> list[dict]:
    users = [dict(row) for row in list_users(conn)]
    for user in users:
        user["roles"] = [dict(row) for row in user_roles(conn, user["id"])]
    return users


def role_exists(conn: sqlite3.Connection, role_id: int) -> bool:
    return conn.execute("SELECT 1 FROM roles WHERE id = ?", (role_id,)).fetchone() is not None
