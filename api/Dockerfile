FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY api/requirements.txt /app/api/requirements.txt
COPY pyproject.toml ARCHITECTURE.md /app/
COPY src/ /app/src/

WORKDIR /app/api
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app
COPY api/ /app/api/
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
