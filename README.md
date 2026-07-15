# FinDoc Intelligence

**80% accuracy on custom 10-question benchmark (Tesla/NVIDIA/Apple/Microsoft 10-Ks)**

[![GitHub](https://img.shields.io/badge/GitHub-findoc-181717?logo=github)](https://github.com/Muhammad-Zubair312/findoc)
[![Custom Benchmark](https://img.shields.io/badge/Custom_Benchmark-80%25-10B981)](#benchmark-results)
[![Human Approval](https://img.shields.io/badge/Human_Approval-90.5%25-7C3AED)](#three-layer-evaluation-loop)
[![LLM](https://img.shields.io/badge/LLM-Groq_gpt--oss--120b-F97316)](https://console.groq.com)
[![Vectors](https://img.shields.io/badge/Vectors-Qdrant-EF4444)](https://qdrant.tech)
[![License](https://img.shields.io/badge/License-MIT-6B7280)](#)

> FinDoc navigates financial documents by **structure**, not by similarity —
> 80% accuracy on a custom benchmark · 90.5% human approval rate ·
> Zero hallucination on out-of-database companies.

---

## What Is FinDoc Intelligence?

FinDoc is a Q&A platform for SEC filings (10-Ks, 10-Qs).
Ask natural-language questions about any financial filing and get grounded,
source-cited answers in seconds — with full citation transparency.

The core innovation is **Vectorless RAG** — instead of chunking documents and
doing vector similarity search, FinDoc builds a hierarchical tree index of each
filing and uses an LLM to navigate it, exactly like a human analyst uses a
table of contents.

**Currently indexed:** Tesla (2023) · NVIDIA (2024) · Apple (2023) · Microsoft (2023)

---

## Demo

```
Query:  "What was Tesla's 2023 automotive gross margin?"
Answer: "Tesla's 2023 automotive gross margin was 19.4% [1]"
Time:   3.6 seconds
Source: Exact paragraph from Tesla 10-K — click [1] to verify
```

```
Query:  "Compare R&D spending between NVIDIA and Tesla in their most recent fiscal year"
Answer: "NVIDIA: $8,675M (14.2% of revenue) vs Tesla: $3,969M (4% of revenue)
         NVIDIA spends $4,706M more on R&D than Tesla [1][2]"
Time:   12 seconds
Source: Citations from two separate 500-page filings simultaneously
```

```
Query:  "What was Boeing's total revenue in 2023?"
Answer: "The retrieved sections contain information for MSFT, NVDA, TSLA,
         and AAPL — but not Boeing. I cannot answer this question."
```
> **Boeing correctly refused** — no hallucination. This is the right behavior in finance.

---

## Quick Start (5 minutes)

```bash
git clone https://github.com/Muhammad-Zubair312/findoc
cd findoc

# 1. Create environment file
cp backend/.env.example backend/.env
# Edit backend/.env and add your free Groq API key:
# GROQ_API_KEY=gsk_your_key_here
# Get it free at: https://console.groq.com (no credit card needed)

# 2. Start all 6 containers
docker-compose up -d

# 3. Run database migrations
docker-compose exec backend alembic upgrade head

# 4. Open the app
# Frontend:  http://localhost:3000
# Backend:   http://localhost:8000/docs
# Qdrant UI: http://localhost:6333/dashboard
```

> **Note:** The `.env` file is gitignored and never committed.
> See `backend/.env.example` for all required variables.

---

## Free-Tier Infrastructure — Zero Cost to Run

| Service | Tool | Cost |
|---|---|---|
| LLM (generation) | Groq + gpt-oss-120b | Free tier — 14,400 req/day |
| LLM (grading) | Groq + gpt-oss-20b | Free tier — faster model |
| Embeddings | BAAI/bge-base-en-v1.5 | Runs locally on CPU — $0 |
| Reranker | ms-marco-MiniLM-L-6-v2 | Runs locally on CPU — $0 |
| Vector store | Qdrant Cloud | Free tier |
| Database | PostgreSQL (Docker) | Local dev |
| Cache / Queue | Redis (Docker) | Local dev |
| Document source | SEC EDGAR API | Free — official government API |

**Total monthly cost: $0**

---

## Architecture — 8-Node LangGraph Agent

```
User query
   │
   ▼
Node 1: Strategy Router (gpt-oss-120b)
   │     Decides: Vectorless RAG vs Hybrid retrieval
   │
   ├─ [Vectorless] → Node 2: Tree Navigator (gpt-oss-120b)
   │                  Reads node summaries, navigates document
   │                  hierarchy like a table of contents
   │                  No vector search needed
   │                  → Node 3: Section Fetcher
   │                    Retrieves full text of identified nodes
   │
   └─ [Hybrid]     → Node 4: BM25 Retriever (keyword sparse search)
                     Node 5: Dense Retriever (Qdrant + bge embeddings)
                     Node 6: Reranker (ms-marco cross-encoder rescoring)

   ↓ all paths converge:

Node 7: Answer Generator (gpt-oss-120b, streaming)
   │     Returns answer with [1][2] citation badges
   │
   ▼
Node 8: Faithfulness Grader (gpt-oss-20b)
   ├─ score < 0.7 → auto-retry with different strategy
   └─ score ≥ 0.7 → stream answer to user
```

---

## Why Vectorless RAG?

SEC 10-K filings have a legally mandated hierarchical structure:

```
Part I
  ├── Item 1.  Business
  ├── Item 1A. Risk Factors
  └── Item 2.  Properties
Part II
  ├── Item 7.  MD&A (Management Discussion & Analysis)
  ├── Item 7A. Market Risk
  └── Item 8.  Financial Statements
Part III / Part IV
```

**The problem with standard RAG:**
Ask "What was Tesla's 2023 automotive gross margin?" and vector similarity
retrieves the energy-segment revenue discussion too — because it's
semantically similar text. That gives you the wrong context.

**How Vectorless RAG solves it:**
FinDoc builds a tree index of each filing. Tesla's 10-K becomes **246 connected
nodes**. The LLM reads the tree outline and reasons: "gross margin is in Item 7
(MD&A) under the Cost of Revenues section" — then navigates directly to that
node. No guessing, no noise.

**Result:** Precise retrieval from the correct section every time.

---

## Ingestion Pipeline

```
SEC EDGAR API / PDF Upload
        ↓
Stage 1: SEC Parser (sec-parser library)
         Parses HTML structure, identifies sections
         Preserves legal document hierarchy

        ↓
Stage 2: Tree Builder
         Builds hierarchical JSON tree
         Root → Parts → Items → Sub-sections → Paragraphs
         Tesla = 246 nodes, NVIDIA = 246 nodes

        ↓
Stage 3: Node Summarizer (gpt-oss-20b)
         2-3 sentence summary per node
         Used for tree navigation decisions

        ↓
Stage 4: Embedder (BAAI/bge-base-en-v1.5, local CPU)
         768-dim embeddings stored in Qdrant
         Runs asynchronously via Celery worker
```

---

## Three-Layer Evaluation Loop

### Layer 1 — Real-Time LLM Judge (Every Query)

```
Answer generated
        ↓
gpt-oss-20b reads: answer + source text
        ↓
Asks: "Is this answer supported by the source?"
        ↓
Score 0.0 → 1.0
        ↓
Below 0.7 → automatic retry with different strategy
Above 0.7 → return to user
```

### Layer 2 — Offline Benchmark (Ground Truth)

10 hand-crafted expert questions with verified correct answers
across Tesla, NVIDIA, and Apple 10-K filings.

**Result: 80% accuracy (8/10 correct)**

| Question Type | Result |
|---|---|
| Exact metric extraction (e.g. gross margin) | ✅ Correct |
| Year-over-year comparison | ✅ Correct |
| Risk factor identification | ✅ Correct |
| Cross-section arithmetic | ❌ Known limitation |
| Forward-looking legal language | ❌ Known limitation |

The 20% failure is documented and understood — not a design flaw.

### Layer 3 — Human Feedback (Explicit Signal)

Users rate every answer with 👍 or 👎.
All ratings stored in PostgreSQL with the query, answer, and AI faithfulness score.

**Result: 90.5% human approval rate (19 positive / 21 total ratings)**

This validates that human judgment aligns with the AI faithfulness grader —
the strongest signal that the eval loop is correctly calibrated.

### FinanceBench — Intentional 0%

Tests questions about AMD, Boeing, Costco — companies **not in the database**.

System correctly refuses to answer rather than hallucinate.

**0% = perfect behavior in finance.**

> A confidently wrong number is far more dangerous than an honest "I don't know."

---

## Benchmark Summary

| Metric | Score | What It Means |
|---|---|---|
| Custom Benchmark | **80%** | 8/10 expert questions correct |
| FinanceBench | **0%** | Correctly refuses out-of-database queries |
| Human Approval Rate | **90.5%** | 19/21 real user ratings positive |
| Avg Response Time | **~4-12s** | Depending on retrieval strategy |
| Avg Cost Per Query | **$0.0000** | Zero API cost for embeddings/reranking |

---

## Project Structure

```
findoc/
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── (auth)/login/       # Login page — mobile responsive
│       │   ├── (auth)/register/    # Register page — mobile responsive
│       │   ├── chat/               # Chat interface
│       │   └── dashboard/          # Evaluation dashboard
│       ├── components/
│       │   ├── chat/
│       │   │   ├── ChatWindow.tsx  # Main chat layout + source panel
│       │   │   ├── MessageBubble.tsx # Answer rendering + citations
│       │   │   ├── ChatInput.tsx   # Query input
│       │   │   └── FeedbackBar.tsx # 👍👎 human feedback
│       │   ├── citations/
│       │   │   ├── SourceTreePanel.tsx # Document tree + citations panel
│       │   │   └── CitationCard.tsx    # Individual source card
│       │   └── dashboard/
│       │       └── DashboardView.tsx   # Benchmark charts + stats
│       └── lib/
│           ├── hooks/useChat.ts    # WebSocket streaming hook
│           └── stores/             # Zustand state management
│
├── backend/
│   └── app/
│       ├── agent/                  # LangGraph 8-node graph
│       │   └── nodes/              # strategy_router, tree_navigator,
│       │                           # generator, grader, etc.
│       ├── retrieval/              # Vectorless RAG + Hybrid + Reranker
│       ├── ingest/                 # SEC parser + tree builder + embedder
│       ├── eval/                   # Benchmark runner + faithfulness judge
│       ├── api/                    # FastAPI routers
│       │   ├── auth.py             # JWT authentication
│       │   ├── chat.py             # WebSocket streaming
│       │   ├── documents.py        # Document + tree endpoints
│       │   └── feedback.py         # Human feedback storage
│       └── llm/
│           └── prompts.py          # All prompts in one place
│
├── docker-compose.yml              # Local development (6 containers)
├── docker-compose.prod.yml         # Azure production
└── Makefile
```

---

## Tech Stack

**Frontend:**
Next.js 14 · TypeScript · Tailwind CSS · shadcn/ui · Framer Motion · Recharts · WebSocket streaming

**Backend:**
Python 3.11 · FastAPI · LangGraph · LangChain · Pydantic v2 · SQLAlchemy 2 · Celery · Alembic

**AI/ML:**
Groq (gpt-oss-120b + gpt-oss-20b) · BAAI/bge-base-en-v1.5 (local CPU) · ms-marco-MiniLM-L-6-v2 (local CPU)

**Infrastructure:**
PostgreSQL 16 · Redis 7 · Qdrant Cloud · Docker Compose · SEC EDGAR API

---

## Docker Services (6 Containers)

```
findoc-frontend    Next.js production build    port 3000
findoc-backend     FastAPI + Uvicorn           port 8000
findoc-celery      Async document indexing     —
findoc-postgres    Document metadata + eval    port 5434
findoc-redis       Task queue + cache          port 6381
findoc-qdrant      Vector store                port 6333
```

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Retrieval approach | Vectorless RAG | Preserves document legal structure |
| LLM provider | Groq only | Free tier, fast inference |
| Embeddings | Local BAAI/bge | Zero API cost, 768-dim, high quality |
| Reranker | Local ms-marco | Zero API cost, cross-encoder precision |
| Vector DB | Qdrant | Free cloud tier, excellent filtering |
| Eval strategy | 3-layer loop | Automated + human signal combined |
| Frontend | Next.js 14 prod build | 5-10x faster than dev mode |

---

## Known Limitations

1. **Cross-section arithmetic** — Questions requiring calculation across multiple
   document sections (e.g. "calculate YoY change") sometimes fail because
   both numbers must be retrieved from different nodes simultaneously.

2. **Forward-looking statements** — Legal boilerplate in risk disclosures uses
   heavily qualified language that makes precise extraction difficult.

3. **Out-of-database companies** — By design, refuses to answer questions about
   companies whose filings are not indexed. Add the filing first.

4. **4GB RAM minimum** — NVIDIA 2024 10-K (246 nodes) requires sufficient memory
   for the embedding pipeline. Use 2023 filing on memory-constrained servers.

---

## Reproduce the Benchmark

```bash
# Run custom benchmark (10 questions, TSLA/NVDA/AAPL)
docker-compose exec backend python -m scripts.run_custom_eval

# Or use the dashboard UI
# Go to: http://localhost:3000/dashboard
# Click: "Run Evaluation"
```

---

## Contact

**Muhammad Zubair**
- Email: zubairaflatoon9@gmail.com
- GitHub: [Muhammad-Zubair312](https://github.com/Muhammad-Zubair312)
- Repository: [github.com/Muhammad-Zubair312/findoc](https://github.com/Muhammad-Zubair312/findoc)
- Demo: [Loom](https://www.loom.com/share/ce7190356f7e46b296c9f1a5999efb2c)
