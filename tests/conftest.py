"""Shared test fixtures."""

import os

# Use in-memory SQLite for tests
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["API_KEY"] = "changeme-dev-key"
os.environ["APP_ENV"] = "development"

import pytest
import pytest_asyncio

from db.models import init_db, close_db, engine, Base


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create fresh DB tables for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
