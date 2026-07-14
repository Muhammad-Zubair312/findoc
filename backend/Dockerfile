FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    poppler-utils \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install poetry && poetry config virtualenvs.create false

COPY pyproject.toml ./
RUN poetry install --no-root --only main

# Pre-download the local embedding model so the container has no cold-start delay
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('BAAI/bge-base-en-v1.5')"

RUN mkdir -p /app/uploads

EXPOSE 8000

FROM base AS dev
RUN poetry install --no-root
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS prod
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
