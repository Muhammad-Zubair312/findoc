#!/bin/bash
set -e

# FinDoc Intelligence — Bootstrap Script
# Starts all services, runs migrations, seeds demo data
# Safe to re-run (idempotent)

echo "╔══════════════════════════════════════════════╗"
echo "║     FinDoc Intelligence — Bootstrap          ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Verify GROQ_API_KEY is set before doing anything
if [ -f ./backend/.env ]; then
  if ! grep -q "^GROQ_API_KEY=gsk_" ./backend/.env; then
    echo "❌ ERROR: GROQ_API_KEY is not set in backend/.env"
    echo "   Get your free key at: https://console.groq.com"
    echo "   Add to backend/.env: GROQ_API_KEY=gsk_your_key_here"
    exit 1
  fi
else
  echo "❌ ERROR: backend/.env not found."
  echo "   Run: cp backend/.env.example backend/.env"
  echo "   Then add your GROQ_API_KEY (free at console.groq.com)"
  exit 1
fi

echo "✓ GROQ_API_KEY found"
echo ""

echo "==> [1/6] Starting Postgres, Redis, Qdrant..."
docker-compose up -d postgres redis qdrant
echo "    Waiting for all services to be healthy (60s max)..."
timeout 60 bash -c 'until docker-compose ps postgres | grep -q "healthy"; do sleep 2; done'
echo "    ✓ Postgres ready"
timeout 60 bash -c 'until docker-compose ps redis | grep -q "healthy"; do sleep 2; done'
echo "    ✓ Redis ready"
timeout 60 bash -c 'until docker-compose ps qdrant | grep -q "healthy"; do sleep 2; done'
echo "    ✓ Qdrant ready"
echo ""

echo "==> [2/6] Running DB migrations..."
docker-compose run --rm backend alembic upgrade head
echo "    ✓ Migrations complete"
echo ""

echo "==> [3/6] Setting up Qdrant collection (768-dim vectors)..."
docker-compose run --rm backend python -m scripts.setup_qdrant_collection
echo "    ✓ Qdrant collection ready"
echo ""

echo "==> [4/6] Downloading FinanceBench dataset..."
docker-compose run --rm backend python -m scripts.download_financebench
echo "    ✓ FinanceBench dataset ready"
echo ""

echo "==> [5/6] Creating demo user..."
docker-compose run --rm backend python -m scripts.create_demo_user
echo "    ✓ Demo user ready: demo@findoc.local / demo1234"
echo ""

echo "==> [6/6] Ingesting sample documents..."
echo "    Fetching Tesla, NVIDIA, Apple 10-Ks from SEC EDGAR..."
echo "    Building tree indices + local embeddings (no API cost for embeddings)..."
echo "    Node summaries via Groq llama-3.1-8b-instant (fast + free)..."
echo "    This takes 5-10 minutes on first run. Grab a coffee. ☕"
docker-compose run --rm backend python -m scripts.seed_sample_docs
echo "    ✓ Sample documents ingested"
echo ""

echo "==> Starting all services..."
docker-compose up -d
echo ""

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ✅ FinDoc Intelligence is running!                      ║"
echo "║                                                          ║"
echo "║  Frontend:   http://localhost:3000                       ║"
echo "║  Backend:    http://localhost:8000/docs                  ║"
echo "║  Qdrant UI:  http://localhost:6333/dashboard             ║"
echo "║                                                          ║"
echo "║  Login: demo@findoc.local / demo1234                     ║"
echo "║                                                          ║"
echo "║  LLM: Groq (llama-3.3-70b) — 14,400 req/day free        ║"
echo "║  Embeddings: Local BAAI/bge-base-en-v1.5 — zero cost     ║"
echo "║  Vectors: Qdrant (local Docker) — zero cost              ║"
echo "╚══════════════════════════════════════════════════════════╝"
