"""Правила расчёта статусов и доступа к ролям.

Статус не хранится в базе: он вычисляется по датам периода и отметке отзыва.
Так автоматическое завершение замещения не зависит от фоновых процессов.
"""

from __future__ import annotations

import sqlite3
from datetime import date

STATUS_PLANNED = "запланировано"
STATUS_ACTIVE = "активно"
STATUS_COMPLETED = "завершено"
STATUS_REVOKED = "отозвано"

STATUS_CLASSES = {
    STATUS_PLANNED: "planned",
    STATUS_ACTIVE: "active",
    STATUS_COMPLETED: "done",
    STATUS_REVOKED: "revoked",
}


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def status_for(date_from: str | date, date_to: str | date, revoked_at: str | None, today: date) -> str:
    if revoked_at:
        return STATUS_REVOKED
    start = date_from if isinstance(date_from, date) else date.fromisoformat(date_from)
    end = date_to if isinstance(date_to, date) else date.fromisoformat(date_to)
    if today < start:
        return STATUS_PLANNED
    if start <= today <= end:
        return STATUS_ACTIVE
    return STATUS_COMPLETED


def status_class(status: str) -> str:
    return STATUS_CLASSES.get(status, "done")


def format_date(value: str | date | None) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value[:10])
        except ValueError:
            return value
    return value.strftime("%d.%m.%Y")


def row_status(row: sqlite3.Row, today: date) -> str:
    return status_for(row["date_from"], row["date_to"], row["revoked_at"], today)


def role_is_transferred(
    conn: sqlite3.Connection,
    role_id: int,
    today: date,
    owner_id: int | None = None,
) -> bool:
    if owner_id is None:
        rows = conn.execute(
            "SELECT date_from, date_to, revoked_at FROM substitutions WHERE role_id = ?",
            (role_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT date_from, date_to, revoked_at
            FROM substitutions
            WHERE role_id = ? AND owner_id = ?
            """,
            (role_id, owner_id),
        ).fetchall()
    return any(row_status(row, today) == STATUS_ACTIVE for row in rows)


def deputy_has_access(conn: sqlite3.Connection, deputy_id: int, role_id: int, today: date) -> bool:
    rows = conn.execute(
        """
        SELECT date_from, date_to, revoked_at
        FROM substitutions
        WHERE deputy_id = ? AND role_id = ?
        """,
        (deputy_id, role_id),
    ).fetchall()
    return any(row_status(row, today) == STATUS_ACTIVE for row in rows)
