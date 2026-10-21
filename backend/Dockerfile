FROM python:3.12-slim

# Bust cache when app code changes materially (password reset, etc.)
ARG MANTIS_API_BUILD=0.2.0

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Render inyecta PORT; localmente usa 8000.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
