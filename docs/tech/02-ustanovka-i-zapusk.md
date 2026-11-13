# Установка и запуск

## Требования

- Python 3.11+ (в контейнере используется python:3.11-slim).
- Зависимости из `substitution_app/requirements.txt`: FastAPI, Uvicorn, Jinja2, python-multipart.
- Внешняя СУБД не нужна: используется файл SQLite.

## Локальный запуск

```bash
python -m venv .venv
.venv/bin/pip install -r substitution_app/requirements.txt
.venv/bin/uvicorn substitution_app.app:app --host 0.0.0.0 --port 8080
```

Тесты:

```bash
.venv/bin/python -m pytest -q
```

## Docker

```bash
docker build -t substitution substitution_app
docker run --rm -p 8080:8080 substitution
```

Dockerfile собирает сервис из каталога `substitution_app`, устанавливает зависимости отдельным слоем с кешем pip и запускает Uvicorn на `0.0.0.0:8080`.

## Переменные окружения

| Переменная | Назначение | Значение по умолчанию |
|---|---|---|
| `COOKIE_SECRET` | Ключ подписи куки сессии | `dev-substitution-secret-key` (значение для стенда) |
| `DATABASE_PATH` | Путь к файлу SQLite | `substitution_app/substitution.db` рядом с кодом |
| `SUBSTITUTION_TODAY` | Фиксация текущей даты (ISO, для демонстрации и автотестов) | не задана, используется текущая дата UTC |

На стенде переменные не требуются: сервис стартует с значениями по умолчанию, создаёт таблицы и начальные данные при старте.

## Проверка живости

- `GET /health` → `200`, текст `ok`.
- `GET /` → `200` (страница входа).

## База данных

Файл `substitution.db` создаётся автоматически. Таблицы: `users`, `roles`, `user_roles`, `substitutions`. Начальные данные создаются только в пустой базе. Для сброса демонстрационных данных остановите сервис и удалите файл базы.
