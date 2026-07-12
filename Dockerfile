# Уникальное имя базы
FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Установка зависимостей системы (нужны для сборки asyncpg/uvloop и т.п.)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Копирование requirements / uv
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv pip install --system -r pyproject.toml

COPY . .

CMD ["python", "-m", "mc_ping_bot.main"]
