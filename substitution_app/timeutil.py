"""Единый источник текущей даты системы.

Все расчёты статусов идут в UTC. Переменная SUBSTITUTION_TODAY позволяет
зафиксировать дату для демонстрации и автотестов, на стенде она не задана.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone


def today() -> date:
    override = os.getenv("SUBSTITUTION_TODAY")
    if override:
        try:
            return date.fromisoformat(override)
        except ValueError:
            pass
    return datetime.now(timezone.utc).date()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
