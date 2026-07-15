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
RUN pip install poetry poetry-plugin-export && poetry config virtualenvs.create false
COPY pyproject.toml ./
RUN poetry config virtualenvs.create false
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu --no-cache-dir
RUN poetry export -f requirements.txt --without-hashes --only main --no-ansi 2>/dev/null | \
    grep -E "^[a-z]" | \
    grep -v "^nvidia-" | \
    grep -v "^triton" | \
    grep -v "^torch" > /tmp/requirements.txt
RUN pip install \
    --retries 10 \
    --timeout 300 \
    --no-cache-dir \
    -r /tmp/requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('BAAI/bge-base-en-v1.5')"
RUN mkdir -p /app/uploads
EXPOSE 8000

FROM base AS dev
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS prod
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]