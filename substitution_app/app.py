"""Веб-сервис «Замещение»: FastAPI + Jinja2 + SQLite."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db, logic
from .auth import (
    COOKIE_NAME,
    csrf_token,
    csrf_valid,
    make_session,
    read_session,
)
from .timeutil import now_iso, today as system_today

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

FLASH_MESSAGES = {
    "created": "Замещение сохранено.",
    "revoked": "Замещение отозвано.",
    "revoked_role": "Все замещения по роли отозваны.",
    "revoked_all": "Все замещения отозваны.",
    "user_created": "Пользователь создан.",
    "role_created": "Роль создана.",
    "roles_saved": "Роли пользователя сохранены.",
}

STATUS_FILTERS = {
    "all": "Все",
    "active": "Активные",
    "planned": "Запланированные",
    "completed": "Завершённые",
    "revoked": "Отозванные",
}

FILTER_KEYS = {
    "active": logic.STATUS_ACTIVE,
    "planned": logic.STATUS_PLANNED,
    "completed": logic.STATUS_COMPLETED,
    "revoked": logic.STATUS_REVOKED,
}


def create_app(db_path: str | Path | None = None) -> FastAPI:
    database = Path(
        db_path
        or os.getenv("DATABASE_PATH")
        or (BASE_DIR / "substitution.db")
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.init_db(database)
        yield

    app = FastAPI(title="Замещение", lifespan=lifespan)
    app.state.db_path = database

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.globals["format_date"] = logic.format_date
    templates.env.globals["status_class"] = logic.status_class

    def get_conn():
        return db.connect(database)

    def current_user(request: Request):
        raw = request.cookies.get(COOKIE_NAME)
        user_id = read_session(raw)
        if user_id is None:
            return None
        conn = get_conn()
        try:
            row = db.get_user(conn, user_id)
        finally:
            conn.close()
        return dict(row) if row else None

    def render(request: Request, name: str, status_code: int = 200, **context):
        user = context.pop("current_user", None)
        if user is None:
            user = current_user(request)
        context.setdefault("current_user", user)
        context.setdefault(
            "csrf_token", csrf_token(user["id"] if user else None)
        )
        return templates.TemplateResponse(
            request, name, context, status_code=status_code
        )

    def redirect(url: str) -> RedirectResponse:
        return RedirectResponse(url=url, status_code=303)

    def load_substitutions(conn, owner_id: int):
        rows = conn.execute(
            """
            SELECT s.*, r.name AS role_name, r.description AS role_description,
                   u.full_name AS deputy_name, u.email AS deputy_email
            FROM substitutions s
            JOIN roles r ON r.id = s.role_id
            JOIN users u ON u.id = s.deputy_id
            WHERE s.owner_id = ?
            ORDER BY s.id
            """,
            (owner_id,),
        ).fetchall()
        current = system_today()
        return [
            {**dict(row), "status": logic.row_status(row, current)}
            for row in rows
        ]

    def load_delegated(conn, deputy_id: int):
        rows = conn.execute(
            """
            SELECT s.*, r.name AS role_name, r.description AS role_description,
                   o.full_name AS owner_name
            FROM substitutions s
            JOIN roles r ON r.id = s.role_id
            JOIN users o ON o.id = s.owner_id
            WHERE s.deputy_id = ?
            ORDER BY s.id
            """,
            (deputy_id,),
        ).fetchall()
        current = system_today()
        result = []
        for row in rows:
            status = logic.row_status(row, current)
            result.append(
                {
                    **dict(row),
                    "status": status,
                    "available": status == logic.STATUS_ACTIVE,
                }
            )
        return result

    def my_roles(conn, user_id: int):
        current = system_today()
        roles = [dict(row) for row in db.user_roles(conn, user_id)]
        for role in roles:
            role["transferred"] = logic.role_is_transferred(
                conn, role["id"], current, owner_id=user_id
            )
            role["available"] = not role["transferred"]
        return roles

    def render_users(request: Request, conn, error: str | None = None, status_code: int = 200):
        return render(
            request,
            "users.html",
            status_code=status_code,
            users=db.users_with_roles(conn),
            roles=db.list_roles(conn),
            error=error,
            flash=FLASH_MESSAGES.get(request.query_params.get("ok", "")),
        )

    @app.get("/health", response_class=PlainTextResponse)
    def health():
        return "ok"

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        conn = get_conn()
        try:
            users = db.list_users(conn)
        finally:
            conn.close()
        return render(request, "login.html", users=users)

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request):
        conn = get_conn()
        try:
            users = db.list_users(conn)
        finally:
            conn.close()
        return render(request, "login.html", users=users)

    @app.post("/login")
    async def login(request: Request):
        form = await request.form()
        user = current_user(request)
        expected_user_id = user["id"] if user else None
        if not csrf_valid(form.get("csrf_token"), expected_user_id):
            raise HTTPException(status_code=400, detail="Недействительный CSRF-токен")
        try:
            user_id = int(form.get("user_id", ""))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Выберите пользователя")
        conn = get_conn()
        try:
            target = db.get_user(conn, user_id)
        finally:
            conn.close()
        if not target:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        response = redirect("/substitutions")
        response.set_cookie(
            COOKIE_NAME,
            make_session(user_id),
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,
        )
        return response

    @app.post("/logout")
    async def logout(request: Request):
        form = await request.form()
        user = current_user(request)
        if not csrf_valid(form.get("csrf_token"), user["id"] if user else None):
            raise HTTPException(status_code=400, detail="Недействительный CSRF-токен")
        response = redirect("/login")
        response.delete_cookie(COOKIE_NAME)
        return response

    @app.get("/substitutions", response_class=HTMLResponse)
    def substitutions_list(request: Request):
        user = current_user(request)
        if not user:
            return redirect("/login")
        conn = get_conn()
        try:
            roles = my_roles(conn, user["id"])
            substitutions = load_substitutions(conn, user["id"])
            delegated = load_delegated(conn, user["id"])
        finally:
            conn.close()

        counts = {status: 0 for status in FILTER_KEYS}
        for item in substitutions:
            for key, value in FILTER_KEYS.items():
                if item["status"] == value:
                    counts[key] += 1

        revocable_role_ids = {
            item["role_id"]
            for item in substitutions
            if item["status"] in (logic.STATUS_PLANNED, logic.STATUS_ACTIVE)
        }

        filter_key = request.query_params.get("status", "all")
        if filter_key not in STATUS_FILTERS:
            filter_key = "all"
        if filter_key != "all":
            substitutions = [
                item for item in substitutions if item["status"] == FILTER_KEYS[filter_key]
            ]

        return render(
            request,
            "substitutions.html",
            roles=roles,
            substitutions=substitutions,
            delegated=delegated,
            counts=counts,
            total_substitutions=sum(counts.values()),
            revocable_role_ids=revocable_role_ids,
            filter_key=filter_key,
            filters=STATUS_FILTERS,
            flash=FLASH_MESSAGES.get(request.query_params.get("ok", "")),
        )

    @app.get("/substitutions/new", response_class=HTMLResponse)
    def substitution_new(request: Request):
        user = current_user(request)
        if not user:
            return redirect("/login")
        conn = get_conn()
        try:
            roles = db.user_roles(conn, user["id"])
            users = [row for row in db.list_users(conn) if row["id"] != user["id"]]
        finally:
            conn.close()
        return render(
            request,
            "new_substitution.html",
            roles=roles,
            users=users,
            errors=[],
            form={"date_from": "", "date_to": ""},
            selected_roles=set(),
            selected_deputies={},
        )

    @app.post("/substitutions")
    async def substitution_create(request: Request):
        user = current_user(request)
        if not user:
            return redirect("/login")
        form = await request.form()
        if not csrf_valid(form.get("csrf_token"), user["id"]):
            raise HTTPException(status_code=400, detail="Недействительный CSRF-токен")

        date_from_raw = (form.get("date_from") or "").strip()
        date_to_raw = (form.get("date_to") or "").strip()
        date_from = logic.parse_date(date_from_raw)
        date_to = logic.parse_date(date_to_raw)

        raw_role_ids = []
        for value in form.getlist("role_ids"):
            try:
                role_id = int(value)
            except (TypeError, ValueError):
                continue
            if role_id not in raw_role_ids:
                raw_role_ids.append(role_id)

        conn = get_conn()
        try:
            owned = {row["id"] for row in db.user_roles(conn, user["id"])}
            all_users = {row["id"] for row in db.list_users(conn)}
        finally:
            conn.close()

        errors: list[str] = []
        if any(role_id not in owned for role_id in raw_role_ids):
            errors.append("Можно передавать только свои роли.")
            status_code = 403
        else:
            status_code = 400

        if not date_from_raw or not date_to_raw:
            errors.append("Укажите период замещения: дату начала и дату окончания.")
        elif not date_from or not date_to:
            errors.append("Укажите корректные даты периода.")
        elif date_to < date_from:
            errors.append("Дата окончания не может быть раньше даты начала.")

        if not raw_role_ids:
            errors.append("Выберите хотя бы одну роль.")

        selected_deputies: dict[int, list[int]] = {}
        self_assignment = False
        missing_user = False
        for role_id in raw_role_ids:
            deputies: list[int] = []
            for value in form.getlist(f"deputies_{role_id}"):
                try:
                    deputy_id = int(value)
                except (TypeError, ValueError):
                    continue
                if deputy_id == user["id"]:
                    self_assignment = True
                if deputy_id not in all_users:
                    missing_user = True
                if deputy_id not in deputies:
                    deputies.append(deputy_id)
            selected_deputies[role_id] = deputies
            if not deputies:
                errors.append("Выберите хотя бы одного заместителя для каждой роли.")

        if self_assignment:
            errors.append("Нельзя назначить заместителем самого себя.")
            status_code = 403
        if missing_user:
            errors.append("Выбранный заместитель не найден.")

        if errors:
            conn = get_conn()
            try:
                roles = db.user_roles(conn, user["id"])
                users = [
                    row for row in db.list_users(conn) if row["id"] != user["id"]
                ]
            finally:
                conn.close()
            return render(
                request,
                "new_substitution.html",
                status_code=status_code,
                roles=roles,
                users=users,
                errors=errors,
                form={"date_from": date_from_raw, "date_to": date_to_raw},
                selected_roles={str(role_id) for role_id in raw_role_ids},
                selected_deputies={
                    str(role_id): {str(deputy_id) for deputy_id in deputies}
                    for role_id, deputies in selected_deputies.items()
                },
            )

        created_at = now_iso()
        conn = get_conn()
        try:
            with conn:
                for role_id in raw_role_ids:
                    for deputy_id in selected_deputies[role_id]:
                        conn.execute(
                            """
                            INSERT INTO substitutions
                                (owner_id, role_id, deputy_id, date_from, date_to, created_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                user["id"],
                                role_id,
                                deputy_id,
                                date_from.isoformat(),
                                date_to.isoformat(),
                                created_at,
                            ),
                        )
        finally:
            conn.close()
        return redirect("/substitutions?ok=created")

    @app.get("/substitutions/{substitution_id}", response_class=HTMLResponse)
    def substitution_card(request: Request, substitution_id: int):
        user = current_user(request)
        if not user:
            return redirect("/login")
        conn = get_conn()
        try:
            row = conn.execute(
                """
                SELECT s.*, r.name AS role_name, r.description AS role_description,
                       o.full_name AS owner_name, u.full_name AS deputy_name
                FROM substitutions s
                JOIN roles r ON r.id = s.role_id
                JOIN users o ON o.id = s.owner_id
                JOIN users u ON u.id = s.deputy_id
                WHERE s.id = ?
                """,
                (substitution_id,),
            ).fetchone()
            history = []
            if row:
                history = conn.execute(
                    """
                    SELECT s.*, r.name AS role_name, u.full_name AS deputy_name
                    FROM substitutions s
                    JOIN roles r ON r.id = s.role_id
                    JOIN users u ON u.id = s.deputy_id
                    WHERE s.owner_id = ? AND s.role_id = ?
                    ORDER BY s.id
                    """,
                    (row["owner_id"], row["role_id"]),
                ).fetchall()
        finally:
            conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Замещение не найдено")
        if user["id"] not in (row["owner_id"], row["deputy_id"]):
            raise HTTPException(status_code=403, detail="Нет доступа к записи")

        current = system_today()
        item = {**dict(row), "status": logic.row_status(row, current)}
        history_items = [
            {**dict(entry), "status": logic.row_status(entry, current)}
            for entry in history
        ]
        return render(
            request,
            "substitution_card.html",
            item=item,
            history=history_items,
            is_owner=user["id"] == row["owner_id"],
        )

    @app.post("/substitutions/{substitution_id}/revoke")
    async def substitution_revoke(request: Request, substitution_id: int):
        user = current_user(request)
        if not user:
            return redirect("/login")
        form = await request.form()
        if not csrf_valid(form.get("csrf_token"), user["id"]):
            raise HTTPException(status_code=400, detail="Недействительный CSRF-токен")

        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM substitutions WHERE id = ?", (substitution_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Замещение не найдено")
            if row["owner_id"] != user["id"]:
                raise HTTPException(status_code=403, detail="Нет доступа к записи")
            if row["revoked_at"] is None:
                status = logic.row_status(row, system_today())
                if status in (logic.STATUS_PLANNED, logic.STATUS_ACTIVE):
                    with conn:
                        conn.execute(
                            "UPDATE substitutions SET revoked_at = ? WHERE id = ?",
                            (now_iso(), substitution_id),
                        )
        finally:
            conn.close()
        return redirect("/substitutions?ok=revoked")

    @app.post("/roles/{role_id}/revoke")
    async def role_revoke(request: Request, role_id: int):
        user = current_user(request)
        if not user:
            return redirect("/login")
        form = await request.form()
        if not csrf_valid(form.get("csrf_token"), user["id"]):
            raise HTTPException(status_code=400, detail="Недействительный CSRF-токен")

        conn = get_conn()
        try:
            owned = conn.execute(
                "SELECT 1 FROM user_roles WHERE user_id = ? AND role_id = ?",
                (user["id"], role_id),
            ).fetchone()
            if not owned:
                raise HTTPException(status_code=403, detail="Роль не принадлежит пользователю")
            rows = conn.execute(
                "SELECT * FROM substitutions WHERE owner_id = ? AND role_id = ?",
                (user["id"], role_id),
            ).fetchall()
            current = system_today()
            to_revoke = [
                row["id"]
                for row in rows
                if row["revoked_at"] is None
                and logic.row_status(row, current)
                in (logic.STATUS_PLANNED, logic.STATUS_ACTIVE)
            ]
            if to_revoke:
                with conn:
                    conn.executemany(
                        "UPDATE substitutions SET revoked_at = ? WHERE id = ?",
                        [(now_iso(), row_id) for row_id in to_revoke],
                    )
        finally:
            conn.close()
        return redirect("/substitutions?ok=revoked_role")

    @app.post("/substitutions/revoke-all")
    async def revoke_all(request: Request):
        user = current_user(request)
        if not user:
            return redirect("/login")
        form = await request.form()
        if not csrf_valid(form.get("csrf_token"), user["id"]):
            raise HTTPException(status_code=400, detail="Недействительный CSRF-токен")

        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM substitutions WHERE owner_id = ?", (user["id"],)
            ).fetchall()
            current = system_today()
            to_revoke = [
                row["id"]
                for row in rows
                if row["revoked_at"] is None
                and logic.row_status(row, current)
                in (logic.STATUS_PLANNED, logic.STATUS_ACTIVE)
            ]
            if to_revoke:
                with conn:
                    conn.executemany(
                        "UPDATE substitutions SET revoked_at = ? WHERE id = ?",
                        [(now_iso(), row_id) for row_id in to_revoke],
                    )
        finally:
            conn.close()
        return redirect("/substitutions?ok=revoked_all")

    @app.get("/delegated", response_class=HTMLResponse)
    def delegated_page(request: Request):
        user = current_user(request)
        if not user:
            return redirect("/login")
        conn = get_conn()
        try:
            delegated = load_delegated(conn, user["id"])
        finally:
            conn.close()
        return render(request, "delegated.html", delegated=delegated)

    @app.get("/users", response_class=HTMLResponse)
    def users_page(request: Request):
        user = current_user(request)
        if not user:
            return redirect("/login")
        conn = get_conn()
        try:
            return render_users(request, conn)
        finally:
            conn.close()

    @app.post("/users")
    async def user_create(request: Request):
        user = current_user(request)
        if not user:
            return redirect("/login")
        form = await request.form()
        if not csrf_valid(form.get("csrf_token"), user["id"]):
            raise HTTPException(status_code=400, detail="Недействительный CSRF-токен")
        full_name = (form.get("full_name") or "").strip()
        email = (form.get("email") or "").strip() or None
        if not full_name:
            conn = get_conn()
            try:
                return render_users(
                    request,
                    conn,
                    error="Укажите ФИО пользователя.",
                    status_code=400,
                )
            finally:
                conn.close()
        conn = get_conn()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO users (full_name, email) VALUES (?, ?)",
                    (full_name, email),
                )
        finally:
            conn.close()
        return redirect("/users?ok=user_created")

    @app.post("/roles")
    async def role_create(request: Request):
        user = current_user(request)
        if not user:
            return redirect("/login")
        form = await request.form()
        if not csrf_valid(form.get("csrf_token"), user["id"]):
            raise HTTPException(status_code=400, detail="Недействительный CSRF-токен")
        name = (form.get("name") or "").strip()
        description = (form.get("description") or "").strip()
        if not name:
            conn = get_conn()
            try:
                return render_users(
                    request,
                    conn,
                    error="Укажите название роли.",
                    status_code=400,
                )
            finally:
                conn.close()
        conn = get_conn()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO roles (name, description) VALUES (?, ?)",
                    (name, description),
                )
        finally:
            conn.close()
        return redirect("/users?ok=role_created")

    @app.post("/users/{user_id}/roles")
    async def user_roles_save(request: Request, user_id: int):
        user = current_user(request)
        if not user:
            return redirect("/login")
        form = await request.form()
        if not csrf_valid(form.get("csrf_token"), user["id"]):
            raise HTTPException(status_code=400, detail="Недействительный CSRF-токен")

        conn = get_conn()
        try:
            target = db.get_user(conn, user_id)
            if not target:
                raise HTTPException(status_code=404, detail="Пользователь не найден")
            role_ids = []
            for value in form.getlist("role_ids"):
                try:
                    role_id = int(value)
                except (TypeError, ValueError):
                    continue
                if role_id not in role_ids:
                    role_ids.append(role_id)
            if any(not db.role_exists(conn, role_id) for role_id in role_ids):
                raise HTTPException(status_code=400, detail="Роль не найдена")
            with conn:
                conn.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
                conn.executemany(
                    "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)",
                    [(user_id, role_id) for role_id in role_ids],
                )
        finally:
            conn.close()
        return redirect("/users?ok=roles_saved")

    return app


app = create_app()
