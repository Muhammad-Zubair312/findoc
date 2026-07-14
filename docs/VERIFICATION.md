# FinDoc Intelligence — Verification Checklist

Complete these steps in order to verify the system works end-to-end.
All steps assume `make bootstrap` has completed successfully.

## Pre-flight

- [ ] 1. `make bootstrap` completes without errors
  - Watch for: "GROQ_API_KEY not set" error (fix: add key to backend/.env)
  - Watch for: Docker not running (fix: start Docker Desktop)
  - Normal: embedding model downloads ~90MB on first run

- [ ] 2. All containers healthy:
  ```bash
  docker-compose ps
  ```
  - postgres, redis, qdrant, backend, celery, frontend all show "healthy" or "Up"

- [ ] 3. Qdrant dashboard shows collection:
  - Open http://localhost:6333/dashboard
  - "findoc_sections" collection exists with vector count > 0

## Authentication

- [ ] 4. Navigate to http://localhost:3000
  - Redirects to /login automatically

- [ ] 5. Login: demo@findoc.local / demo1234
  - Lands on /chat page

## Documents

- [ ] 6. Click "Documents" in the left nav
  - Shows Tesla, NVIDIA, Apple 10-Ks with green "Ready" status dot

- [ ] 7. Hover over Tesla 10-K card
  - Shows page count, node count, filing date

## Vectorless RAG — Structural Query

- [ ] 8. Click "Open in Chat" on the Tesla 10-K card
  - Returns to /chat with Tesla selected in DocumentSelector

- [ ] 9. Source tree panel appears on the right side
  - Shows Tesla's filing hierarchy (Part I, Part II, etc.) as a collapsible tree

- [ ] 10. Send: "What was Tesla's 2023 automotive gross margin?"
  - Streaming tokens appear immediately

- [ ] 11. Strategy badge = purple "Vectorless" at top-right of the assistant message
  - Hover the badge to see the routing reasoning

- [ ] 12. Citations panel (right column, Citations tab) shows:
  - At least 1 citation referencing Item 7 or Item 8 sections
  - Each citation shows section title + page range + text excerpt

- [ ] 13. Click a citation card → "Read full section →" link
  - Opens modal with full section text

- [ ] 14. Tree tab: referenced nodes are highlighted
  - The nodes used to answer the question show accent-purple background

## Hybrid RAG — Cross-Document Query

- [ ] 15. Click the DocumentSelector in the chat input
  - Select BOTH Tesla AND Apple 10-Ks

- [ ] 16. Send: "Compare 2023 R&D spending: Tesla vs Apple"
  - Strategy badge = blue "Hybrid"
  - Answer compares both companies with citations from each document

## Direct LLM — No Retrieval

- [ ] 17. Send: "What is EBITDA?"
  - Strategy badge = gray "Direct"
  - Answer is a clear definition with no document citations needed

## Feedback

- [ ] 18. Click thumbs down (👎) on any assistant message
  - Button turns red, toast appears
  - Verify in DB:
  ```bash
  docker-compose exec postgres psql -U findoc -c \
    "SELECT score, reason_text, created_at FROM feedback ORDER BY created_at DESC LIMIT 1;"
  ```

## Dashboard + Eval

- [ ] 19. Navigate to /dashboard
  - MetricCards render (may show zeros before eval runs)
  - No console errors

- [ ] 20. Run a FinanceBench sample:
  ```bash
  docker-compose run --rm backend \
    python -m app.eval.financebench_runner --sample 10
  ```
  - Completes in ~3-5 minutes (10 questions × Groq API calls)
  - Prints overall accuracy score

- [ ] 21. Refresh /dashboard
  - New EvalRun row appears in charts
  - FinanceBench Accuracy MetricCard shows a real percentage
  - FailureInspector shows all 10 questions with expand/collapse

- [ ] 22. Expand a failure row in FailureInspector
  - Shows: predicted answer, gold answer, retrieved sections, reasoning trace

## Persistence Test

- [ ] 23. Run: `docker-compose down && docker-compose up -d`
  - After restart, documents still show on /documents page
  - Qdrant still has vectors (qdrant_data volume persisted)
  - Login still works (Postgres data persisted)

## Idempotency Test

- [ ] 24. Run: `make bootstrap` a second time
  - Completes without errors
  - No duplicate documents, no duplicate demo user
  - "already exists, skipping" messages appear for seeded data

## E2E Automated Test

- [ ] 25. Run:
  ```bash
  docker-compose run --rm backend pytest tests/e2e/test_flow.py -v
  ```
  - All assertions pass
  - Output shows strategy_used, token count, latency_ms

---

## If Something Fails

**"GROQ_API_KEY not set"**
→ Open backend/.env, add: GROQ_API_KEY=gsk_your_key_from_console.groq.com

**"Connection refused" on port 8000**
→ Run: `docker-compose logs backend | tail -50`
→ Look for import errors or missing env vars

**"Qdrant collection not found"**
→ Run: `docker-compose run --rm backend python -m scripts.setup_qdrant_collection`

**"Documents show Processing forever"**
→ Check Celery: `docker-compose logs celery | tail -50`
→ Usually a missing env var or Groq rate limit hit

**"Strategy badge not showing"**
→ Open browser DevTools → Network → check the WebSocket messages
→ Verify "end" event has strategy_used field set

**"FinanceBench runner hits rate limit"**
→ Increase EVAL_DELAY_SECS to 1.0 in backend/.env and retry
