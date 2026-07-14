"""End-to-end flow test. Requires all Docker services running.

Run with: docker-compose exec backend pytest tests/e2e/test_flow.py -v
(uses the already-running `backend` service; `docker-compose run --rm backend
...` also works since it joins the same compose network and resolves the
`backend` hostname to the running service container.)
"""

import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest
import websockets

_HOST = os.environ.get("E2E_HOST", "backend")
BASE = f"http://{_HOST}:8000/api/v1"
WS = f"ws://{_HOST}:8000/api/v1"


@pytest.mark.asyncio
async def test_full_flow() -> None:
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as client:
        # 1. Register
        r = await client.post(
            "/auth/register",
            json={
                "email": "e2e@test.local",
                "password": "Test1234!",
                "full_name": "E2E Test",
            },
        )
        assert r.status_code in (200, 201, 409)  # 409 = already exists (idempotent)

        # 2. Login
        r = await client.post(
            "/auth/login",
            json={"email": "e2e@test.local", "password": "Test1234!"},
        )
        assert r.status_code == 200
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Upload mini 10-K
        pdf_path = Path(__file__).parent.parent / "fixtures" / "mini_10k.pdf"
        assert pdf_path.exists(), "tests/fixtures/mini_10k.pdf must exist"
        r = await client.post(
            "/documents/upload",
            files={"file": ("mini_10k.pdf", pdf_path.read_bytes(), "application/pdf")},
            headers=headers,
        )
        assert r.status_code == 201
        doc_id = r.json()["document"]["id"]

        # 4. Poll ingestion progress
        status = None
        for _ in range(60):
            r = await client.get(f"/documents/{doc_id}", headers=headers)
            status = r.json()["ingest_status"]
            if status == "ready":
                break
            if status == "failed":
                pytest.fail(f"Ingestion failed: {r.json().get('ingest_error')}")
            await asyncio.sleep(2)
        assert status == "ready", f"Ingest did not complete in 120s (status={status})"

        # 5. WebSocket chat — send a query, verify streaming
        uri = f"{WS}/chat/ws?token={token}"
        events = []
        async with websockets.connect(uri) as ws:
            await ws.send(
                json.dumps(
                    {
                        "conversation_id": None,
                        "message": "What is the main business described in this document?",
                        "document_ids": [doc_id],
                        "session_id": "e2e-test-session",
                    }
                )
            )
            async for raw in ws:
                event = json.loads(raw)
                events.append(event)
                if event.get("type") == "end":
                    break

        event_types = [e["type"] for e in events]
        assert "start" in event_types, "Missing 'start' event"
        assert "end" in event_types, "Missing 'end' event"
        token_events = [e for e in events if e["type"] == "token"]
        assert len(token_events) >= 5, f"Too few tokens: {len(token_events)}"
        end_event = next(e for e in events if e["type"] == "end")
        assert end_event.get("strategy_used"), "strategy_used not set in 'end' event"

        # 6. Verify message persisted in DB
        r = await client.get("/conversations", headers=headers)
        assert r.status_code == 200
        convs = r.json()["items"]
        assert len(convs) > 0, "No conversations found after chat"

        # 7. Feedback
        conv_id = convs[0]["id"]
        r = await client.get(f"/conversations/{conv_id}", headers=headers)
        messages = r.json()["messages"]
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert len(assistant_msgs) > 0
        msg_id = assistant_msgs[0]["id"]

        r = await client.post(
            "/feedback", json={"message_id": msg_id, "score": 1}, headers=headers
        )
        assert r.status_code == 201

        print("\n✅ All e2e checks passed")
        print(f"   strategy_used: {end_event['strategy_used']}")
        print(f"   token count:   {len(token_events)}")
        print(f"   latency_ms:    {end_event.get('latency_ms')}")
