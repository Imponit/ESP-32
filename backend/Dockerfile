FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini seed.py ./

RUN pip install --no-cache-dir .

EXPOSE 8000

# Бот-сервис использует этот же образ с command: python -m app.bot.main
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
