"""Tests for FastAPI endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

API_KEY = "changeme-dev-key"
HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_create_task():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/task",
            json={"message": "Erstelle eine LinkedIn Strategie"},
            headers=HEADERS,
        )
        assert r.status_code == 202
        data = r.json()
        assert "task_id" in data
        assert data["status"] in ["pending", "routing", "in_progress", "completed"]


@pytest.mark.asyncio
async def test_create_task_no_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/task",
            json={"message": "Test"},
        )
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_task_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            "/api/v1/task/nonexistent",
            headers=HEADERS,
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_tasks():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/tasks", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert "tasks" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_list_departments():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/departments", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 6
        names = {d["name"] for d in data}
        assert "marketing" in names
        assert "consulting" in names


@pytest.mark.asyncio
async def test_teams_webhook():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/webhook/teams",
            json={"message": "Webhook test", "sender": "ceo"},
            headers=HEADERS,
        )
        assert r.status_code == 202


@pytest.mark.asyncio
async def test_teams_webhook_empty():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/webhook/teams",
            json={},
            headers=HEADERS,
        )
        assert r.status_code == 400
