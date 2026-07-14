"""Document API: ownership checks, upload validation, list/get/delete lifecycle.

EDGAR-backed endpoints (/documents/edgar, /documents/sample-load) make real network
calls to SEC EDGAR and are exercised manually rather than in this automated suite.
Real ingestion (Celery worker + Qdrant + a live Groq key) is likewise out of scope
here — these tests only cover the synchronous API-layer behavior.
"""

import asyncio
import json
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis

from app.config import settings

pytestmark = pytest.mark.asyncio

_MIN_PDF = b"%PDF-1.4\n%mock pdf content for upload validation\n%%EOF"


async def _register_and_login(client: AsyncClient) -> dict:
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Test User"},
    )
    assert resp.status_code == 201
    return resp.json()


async def test_list_documents_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/documents")
    assert resp.status_code == 401


async def test_upload_rejects_non_pdf(client: AsyncClient) -> None:
    await _register_and_login(client)
    resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("notes.txt", b"just some text", "text/plain")},
    )
    assert resp.status_code == 400


async def test_upload_rejects_oversized_file(client: AsyncClient) -> None:
    await _register_and_login(client)
    oversized = b"%PDF-1.4\n" + b"0" * (20 * 1024 * 1024 + 1)
    resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("big.pdf", oversized, "application/pdf")},
    )
    assert resp.status_code == 413


async def test_upload_accepts_valid_pdf_and_enqueues_ingestion(client: AsyncClient) -> None:
    await _register_and_login(client)
    resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("filing.pdf", _MIN_PDF, "application/pdf")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["document"]["ingest_status"] == "pending"
    assert body["document"]["filename"] == "filing.pdf"
    assert body["progress_url"] == f"/api/v1/documents/{body['document']['id']}/progress"


async def test_list_documents_only_returns_own_docs(client: AsyncClient) -> None:
    await _register_and_login(client)
    upload_resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("mine.pdf", _MIN_PDF, "application/pdf")},
    )
    my_doc_id = upload_resp.json()["document"]["id"]

    list_resp = await client.get("/api/v1/documents")
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == my_doc_id

    client.cookies.clear()
    await _register_and_login(client)
    other_list_resp = await client.get("/api/v1/documents")
    assert other_list_resp.json()["total"] == 0


async def test_get_document_not_found(client: AsyncClient) -> None:
    await _register_and_login(client)
    resp = await client.get(f"/api/v1/documents/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_document_forbidden_for_non_owner(client: AsyncClient) -> None:
    await _register_and_login(client)
    upload_resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("owned.pdf", _MIN_PDF, "application/pdf")},
    )
    doc_id = upload_resp.json()["document"]["id"]

    client.cookies.clear()
    await _register_and_login(client)
    resp = await client.get(f"/api/v1/documents/{doc_id}")
    assert resp.status_code == 403


async def test_get_document_detail_has_no_tree_before_ingestion(client: AsyncClient) -> None:
    await _register_and_login(client)
    upload_resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("owned.pdf", _MIN_PDF, "application/pdf")},
    )
    doc_id = upload_resp.json()["document"]["id"]

    resp = await client.get(f"/api/v1/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["tree"] is None


async def test_delete_document_soft_deletes(client: AsyncClient) -> None:
    await _register_and_login(client)
    upload_resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("to_delete.pdf", _MIN_PDF, "application/pdf")},
    )
    doc_id = upload_resp.json()["document"]["id"]

    delete_resp = await client.delete(f"/api/v1/documents/{doc_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {"success": True}

    get_resp = await client.get(f"/api/v1/documents/{doc_id}")
    assert get_resp.status_code == 404

    list_resp = await client.get("/api/v1/documents")
    assert list_resp.json()["total"] == 0


async def test_delete_forbidden_for_non_owner(client: AsyncClient) -> None:
    await _register_and_login(client)
    upload_resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("owned.pdf", _MIN_PDF, "application/pdf")},
    )
    doc_id = upload_resp.json()["document"]["id"]

    client.cookies.clear()
    await _register_and_login(client)
    resp = await client.delete(f"/api/v1/documents/{doc_id}")
    assert resp.status_code == 403


async def test_progress_stream_forbidden_for_non_owner(client: AsyncClient) -> None:
    await _register_and_login(client)
    upload_resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("owned.pdf", _MIN_PDF, "application/pdf")},
    )
    doc_id = upload_resp.json()["document"]["id"]

    client.cookies.clear()
    await _register_and_login(client)
    resp = await client.get(f"/api/v1/documents/{doc_id}/progress")
    assert resp.status_code == 403


async def test_progress_stream_opens_for_owner(client: AsyncClient) -> None:
    await _register_and_login(client)
    upload_resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("owned.pdf", _MIN_PDF, "application/pdf")},
    )
    doc_id = upload_resp.json()["document"]["id"]

    async def consume() -> tuple[int, str, dict[str, Any]]:
        async with client.stream("GET", f"/api/v1/documents/{doc_id}/progress") as resp:
            status_code = resp.status_code
            content_type = resp.headers["content-type"]
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    return status_code, content_type, json.loads(line.removeprefix("data: "))
            return status_code, content_type, {}

    consume_task = asyncio.create_task(consume())
    await asyncio.sleep(0.3)  # let the server subscribe before we publish

    publisher = Redis.from_url(settings.REDIS_URL)
    await publisher.publish(f"doc_progress:{doc_id}", json.dumps({"status": "ready"}))
    await publisher.aclose()

    status_code, content_type, event = await asyncio.wait_for(consume_task, timeout=5.0)
    assert status_code == 200
    assert "text/event-stream" in content_type
    assert event == {"status": "ready"}
