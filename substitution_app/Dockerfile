FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /tmp/requirements.txt

COPY . /ctx
RUN if [ -d /ctx/substitution_app ]; then \
        cp -a /ctx/substitution_app /app/substitution_app; \
    else \
        cp -a /ctx /app/substitution_app; \
    fi \
    && rm -rf /ctx

EXPOSE 8080

CMD ["uvicorn", "substitution_app.app:app", "--host", "0.0.0.0", "--port", "8080"]
