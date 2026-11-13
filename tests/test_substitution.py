from __future__ import annotations

import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from substitution_app.app import create_app
from substitution_app import logic

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "test.db")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def today(monkeypatch):
    def _set(value: str) -> None:
        monkeypatch.setenv("SUBSTITUTION_TODAY", value)

    return _set


def csrf(client: TestClient, path: str) -> str:
    response = client.get(path)
    assert response.status_code == 200, response.text
    match = CSRF_RE.search(response.text)
    assert match, f"CSRF-токен не найден на {path}"
    return match.group(1)


def login(client: TestClient, user_id: int):
    token = csrf(client, "/login")
    response = client.post(
        "/login",
        data={"user_id": str(user_id), "csrf_token": token},
        follow_redirects=True,
    )
    assert response.status_code == 200, response.text
    return response


def create_substitution(client: TestClient, date_from: str, date_to: str, roles: dict[int, list[int]]):
    token = csrf(client, "/substitutions/new")
    data = {
        "csrf_token": token,
        "date_from": date_from,
        "date_to": date_to,
        "role_ids": [str(role_id) for role_id in roles],
    }
    for role_id, deputies in roles.items():
        data[f"deputies_{role_id}"] = [str(deputy_id) for deputy_id in deputies]
    return client.post("/substitutions", data=data, follow_redirects=True)


def rows(client: TestClient):
    conn = sqlite3.connect(client.app.state.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM substitutions ORDER BY id").fetchall()
    finally:
        conn.close()


def role_id_by_name(client: TestClient, name: str) -> int:
    conn = sqlite3.connect(client.app.state.db_path)
    try:
        return conn.execute("SELECT id FROM roles WHERE name = ?", (name,)).fetchone()[0]
    finally:
        conn.close()


def delegated_page(client: TestClient, user_id: int) -> str:
    login(client, user_id)
    response = client.get("/delegated")
    assert response.status_code == 200
    return response.text


def test_case_1_three_roles_to_three_users(client, today):
    today("2025-07-05")
    login(client, 1)
    response = create_substitution(
        client, "2025-07-01", "2025-07-15", {1: [2], 2: [3], 3: [4]}
    )
    assert "Замещение сохранено." in response.text
    assert response.text.count("активно") == 3
    assert response.text.count("недоступна") == 3

    body_b = delegated_page(client, 2)
    assert "Р1" in body_b
    assert "Р2" not in body_b
    assert "доступна" in body_b
    assert "недоступна" not in body_b

    body_c = delegated_page(client, 3)
    assert "Р2" in body_c
    assert "доступна" in body_c

    body_d = delegated_page(client, 4)
    assert "Р3" in body_d
    assert "доступна" in body_d


def test_case_2_period_ends_and_roles_return(client, today):
    today("2025-07-05")
    login(client, 1)
    create_substitution(client, "2025-07-01", "2025-07-15", {1: [2], 2: [3], 3: [4]})
    today("2025-07-16")
    response = client.get("/substitutions")
    assert response.text.count("завершено") == 3
    assert response.text.count("доступна") >= 3

    body_b = delegated_page(client, 2)
    assert "завершено" in body_b
    assert "недоступна" in body_b


def test_case_3_revoke_only_role_two_line(client, today):
    today("2025-07-05")
    login(client, 1)
    create_substitution(client, "2025-07-01", "2025-07-15", {1: [2], 2: [3], 3: [4]})
    r2_row = next(row for row in rows(client) if row["role_id"] == role_id_by_name(client, "Р2"))

    token = csrf(client, "/substitutions")
    response = client.post(
        f"/substitutions/{r2_row['id']}/revoke",
        data={"csrf_token": token},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Замещение отозвано." in response.text
    assert "отозвано" in response.text

    body_b = delegated_page(client, 2)
    assert "доступна" in body_b
    body_c = delegated_page(client, 3)
    assert "недоступна" in body_c
    body_d = delegated_page(client, 4)
    assert "доступна" in body_d


def test_case_4_revoke_all(client, today):
    today("2025-07-05")
    login(client, 1)
    create_substitution(client, "2025-07-01", "2025-07-15", {1: [2], 2: [3], 3: [4]})
    token = csrf(client, "/substitutions")
    response = client.post(
        "/substitutions/revoke-all",
        data={"csrf_token": token},
        follow_redirects=True,
    )
    assert "Все замещения отозваны." in response.text
    assert all(row["revoked_at"] for row in rows(client))
    assert response.text.count("недоступна") == 0

    body_b = delegated_page(client, 2)
    assert "недоступна" in body_b


def test_case_5_second_deputy_on_overlapping_period(client, today):
    today("2025-07-05")
    login(client, 1)
    create_substitution(client, "2025-07-01", "2025-07-15", {1: [2]})
    response = create_substitution(client, "2025-07-10", "2025-07-20", {1: [5]})
    assert "Замещение сохранено." in response.text
    assert len(rows(client)) == 2
    assert response.text.count("недоступна") == 1

    assert "доступна" in delegated_page(client, 2)
    assert "доступна" in delegated_page(client, 5)


def test_case_6_only_transferred_roles_are_in_list(client, today):
    today("2025-07-05")
    login(client, 1)
    create_substitution(client, "2025-07-01", "2025-07-15", {1: [2], 2: [3]})
    response = client.get("/substitutions")
    assert "Р3" in response.text
    assert "доступна" in response.text
    assert {row["role_id"] for row in rows(client)} == {
        role_id_by_name(client, "Р1"),
        role_id_by_name(client, "Р2"),
    }
    assert len(rows(client)) == 2


def test_case_7_overlapping_periods_availability(client, today):
    today("2025-07-01")
    login(client, 1)
    create_substitution(client, "2025-07-01", "2025-07-15", {1: [2]})
    create_substitution(client, "2025-07-10", "2025-07-20", {1: [3]})
    r1 = role_id_by_name(client, "Р1")
    conn = sqlite3.connect(client.app.state.db_path)
    conn.row_factory = sqlite3.Row
    try:
        expected = {
            "2025-07-01": (True, False),
            "2025-07-09": (True, False),
            "2025-07-10": (True, True),
            "2025-07-15": (True, True),
            "2025-07-16": (False, True),
            "2025-07-20": (False, True),
            "2025-07-21": (False, False),
        }
        for value, (b_access, v_access) in expected.items():
            day = logic.parse_date(value)
            assert logic.deputy_has_access(conn, 2, r1, day) is b_access
            assert logic.deputy_has_access(conn, 3, r1, day) is v_access
            assert logic.role_is_transferred(conn, r1, day, owner_id=1) is (b_access or v_access)
    finally:
        conn.close()


def test_case_8_revoke_one_deputy_keeps_other(client, today):
    today("2025-07-05")
    login(client, 1)
    create_substitution(client, "2025-07-01", "2025-07-15", {1: [2, 5]})
    first = rows(client)[0]
    token = csrf(client, "/substitutions")
    response = client.post(
        f"/substitutions/{first['id']}/revoke",
        data={"csrf_token": token},
        follow_redirects=True,
    )
    assert "Замещение отозвано." in response.text
    assert response.text.count("недоступна") == 1

    body_b = delegated_page(client, 2)
    assert "недоступна" in body_b
    body_d = delegated_page(client, 5)
    assert "доступна" in body_d


def test_case_9_revoke_role_entirely(client, today):
    today("2025-07-05")
    login(client, 1)
    create_substitution(client, "2025-07-01", "2025-07-15", {1: [2, 5]})
    r1 = role_id_by_name(client, "Р1")
    token = csrf(client, "/substitutions")
    response = client.post(
        f"/roles/{r1}/revoke",
        data={"csrf_token": token},
        follow_redirects=True,
    )
    assert "Все замещения по роли отозваны." in response.text
    assert all(row["revoked_at"] for row in rows(client))
    assert "недоступна" not in response.text

    assert "недоступна" in delegated_page(client, 2)
    assert "недоступна" in delegated_page(client, 5)


def test_case_10_future_period_is_planned(client, today):
    today("2025-07-25")
    login(client, 1)
    response = create_substitution(client, "2025-08-01", "2025-08-15", {1: [2]})
    assert "Замещение сохранено." in response.text
    assert "запланировано" in response.text
    assert "доступна" in response.text

    body_b = delegated_page(client, 2)
    assert "запланировано" in body_b
    assert "недоступна" in body_b


def test_case_11_end_before_start_is_rejected(client, today):
    today("2025-07-05")
    login(client, 1)
    response = create_substitution(client, "2025-07-15", "2025-07-01", {1: [2]})
    assert response.status_code == 400
    assert "Дата окончания не может быть раньше даты начала." in response.text
    assert rows(client) == []


def test_case_12_deputy_access_only_inside_period(client, today):
    today("2025-06-30")
    login(client, 1)
    create_substitution(client, "2025-07-01", "2025-07-15", {1: [2]})
    r1 = role_id_by_name(client, "Р1")

    body = delegated_page(client, 2)
    assert "недоступна" in body
    login(client, 1)
    body = client.get("/substitutions")
    assert "доступна" in body.text

    today("2025-07-10")
    assert "доступна" in delegated_page(client, 2)
    login(client, 1)
    body = client.get("/substitutions")
    assert "недоступна" in body.text

    today("2025-07-16")
    assert "недоступна" in delegated_page(client, 2)
    login(client, 1)
    body = client.get("/substitutions")
    assert "доступна" in body.text

    conn = sqlite3.connect(client.app.state.db_path)
    conn.row_factory = sqlite3.Row
    try:
        assert logic.deputy_has_access(conn, 2, r1, logic.parse_date("2025-06-30")) is False
        assert logic.deputy_has_access(conn, 2, r1, logic.parse_date("2025-07-01")) is True
        assert logic.deputy_has_access(conn, 2, r1, logic.parse_date("2025-07-15")) is True
        assert logic.deputy_has_access(conn, 2, r1, logic.parse_date("2025-07-16")) is False
    finally:
        conn.close()


def test_case_13_create_user_and_assign_role(client, today):
    today("2025-07-05")
    login(client, 1)
    token = csrf(client, "/users")
    response = client.post(
        "/users",
        data={
            "csrf_token": token,
            "full_name": "Новый Сотрудник",
            "email": "new@example.com",
        },
        follow_redirects=True,
    )
    assert "Пользователь создан." in response.text
    assert "Новый Сотрудник" in response.text

    conn = sqlite3.connect(client.app.state.db_path)
    try:
        new_id = conn.execute(
            "SELECT id FROM users WHERE full_name = ?", ("Новый Сотрудник",)
        ).fetchone()[0]
    finally:
        conn.close()

    token = csrf(client, "/users")
    response = client.post(
        f"/users/{new_id}/roles",
        data={"csrf_token": token, "role_ids": "1"},
        follow_redirects=True,
    )
    assert "Роли пользователя сохранены." in response.text

    conn = sqlite3.connect(client.app.state.db_path)
    try:
        assigned = conn.execute(
            "SELECT role_id FROM user_roles WHERE user_id = ?", (new_id,)
        ).fetchall()
    finally:
        conn.close()
    assert [row[0] for row in assigned] == [1]

    response = client.get("/substitutions/new")
    assert "Новый Сотрудник" in response.text


def test_cannot_revoke_foreign_substitution(client, today):
    today("2025-07-05")
    login(client, 1)
    create_substitution(client, "2025-07-01", "2025-07-15", {1: [2]})
    substitution_id = rows(client)[0]["id"]

    login(client, 2)
    token = csrf(client, "/substitutions")
    response = client.post(
        f"/substitutions/{substitution_id}/revoke",
        data={"csrf_token": token},
    )
    assert response.status_code == 403


def test_cannot_assign_self_as_deputy(client, today):
    today("2025-07-05")
    login(client, 1)
    response = create_substitution(client, "2025-07-01", "2025-07-15", {1: [1]})
    assert response.status_code == 403
    assert "Нельзя назначить заместителем самого себя." in response.text
    assert rows(client) == []


def test_cannot_transfer_foreign_role(client, today):
    today("2025-07-05")
    login(client, 1)
    token = csrf(client, "/substitutions/new")
    response = client.post(
        "/substitutions",
        data={
            "csrf_token": token,
            "date_from": "2025-07-01",
            "date_to": "2025-07-15",
            "role_ids": "1",
            "deputies_1": "2",
        },
    )
    assert response.status_code == 200

    login(client, 2)
    token = csrf(client, "/substitutions/new")
    response = client.post(
        "/substitutions",
        data={
            "csrf_token": token,
            "date_from": "2025-07-01",
            "date_to": "2025-07-15",
            "role_ids": "1",
            "deputies_1": "3",
        },
    )
    assert response.status_code == 403
    assert "Можно передавать только свои роли." in response.text


def test_role_requires_deputy(client, today):
    today("2025-07-05")
    login(client, 1)
    token = csrf(client, "/substitutions/new")
    response = client.post(
        "/substitutions",
        data={
            "csrf_token": token,
            "date_from": "2025-07-01",
            "date_to": "2025-07-15",
            "role_ids": "1",
        },
    )
    assert response.status_code == 400
    assert "Выберите хотя бы одного заместителя для каждой роли." in response.text
    assert rows(client) == []


def test_csrf_is_required(client, today):
    today("2025-07-05")
    login(client, 1)
    response = client.post(
        "/substitutions",
        data={
            "date_from": "2025-07-01",
            "date_to": "2025-07-15",
            "role_ids": "1",
            "deputies_1": "2",
        },
    )
    assert response.status_code == 400
    assert rows(client) == []


def test_admin_can_create_role(client, today):
    today("2025-07-05")
    login(client, 1)
    token = csrf(client, "/users")
    response = client.post(
        "/roles",
        data={"csrf_token": token, "name": "Р4", "description": "Новая роль"},
        follow_redirects=True,
    )
    assert "Роль создана." in response.text
    assert "Р4" in response.text

    conn = sqlite3.connect(client.app.state.db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM roles WHERE name = 'Р4'").fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_delegation_does_not_block_role_of_another_owner(client, today):
    today("2025-07-05")
    login(client, 1)
    create_substitution(client, "2025-07-01", "2025-07-15", {1: [2]})

    token = csrf(client, "/users")
    client.post(
        "/users/3/roles",
        data={"csrf_token": token, "role_ids": "1"},
        follow_redirects=True,
    )

    login(client, 3)
    response = client.get("/substitutions")
    assert "Р1" in response.text
    assert "доступна" in response.text
    assert "недоступна" not in response.text


def test_health_and_root_are_alive(client):
    assert client.get("/health").text == "ok"
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200


def test_badges_are_rendered_lowercase_for_scenarios(client, today):
    today("2025-07-05")
    login(client, 1)
    response = create_substitution(client, "2025-07-01", "2025-07-15", {1: [2]})
    assert "<span class=\"badge active\">активно</span>" in response.text

    stylesheet = client.get("/static/style.css")
    assert stylesheet.status_code == 200
    assert "text-transform:capitalize" not in stylesheet.text


def test_status_filter_and_counts_use_russian_statuses(client, today):
    today("2025-07-05")
    login(client, 1)
    create_substitution(client, "2025-07-01", "2025-07-15", {1: [2]})

    active = client.get("/substitutions?status=active")
    assert active.status_code == 200
    assert "Пользователь Б" in active.text
    assert "недоступна" in active.text

    planned = client.get("/substitutions?status=planned")
    assert planned.status_code == 200
    assert "Пользователь Б" not in planned.text
