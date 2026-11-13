# Сервис «Замещение»

Веб-приложение для передачи ролей пользователя заместителям на период, досрочного отзыва и автоматического возврата ролей по окончании периода.

- Стек: Python 3.11, FastAPI, Jinja2, SQLite.
- Запуск: `uvicorn substitution_app.app:app --host 0.0.0.0 --port 8080`.
- Проверка живости: `GET /health`, `GET /`.
- Тесты: `.venv/bin/python -m pytest -q`.

Документация:

- [Настройка замещения](docs/business/01-kak-nastroit-zameshcheniya.md)
- [Разные роли — разным людям](docs/business/02-raznye-roli-raznym-lyudyam.md)
- [Досрочный отзыв](docs/business/03-kak-dosrochno-otozvat.md)
- [Сроки и статусы](docs/business/04-sroki-i-statusy.md)
- [FAQ](docs/business/05-faq.md)
- [Администратор](docs/tech/01-administrator.md)
- [Установка и запуск](docs/tech/02-ustanovka-i-zapusk.md)
- [Интерфейсы](docs/tech/03-interfejsy.md)
