"""Shared test setup: a separate `doctoo_test` database and captured emails."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.models import Base
from app.services.email import EmailMessage, get_email_sender

_base_url, _db_name = get_settings().database_url.rsplit("/", 1)
TEST_DATABASE_URL = f"{_base_url}/{_db_name}_test"


class Outbox:
    """Collects emails instead of sending them."""

    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)

    def last_link(self) -> str:
        """The URL in the most recent email."""
        body = self.messages[-1].body
        return next(word for word in body.split() if word.startswith("http"))

    def last_token(self) -> str:
        return self.last_link().split("token=", 1)[1]


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    admin = create_async_engine(get_settings().database_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": f"{_db_name}_test"}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{_db_name}_test"'))
    await admin.dispose()

    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def outbox() -> Outbox:
    return Outbox()


@pytest.fixture
async def client(engine: AsyncEngine, outbox: Outbox) -> AsyncIterator[AsyncClient]:
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_email_sender] = lambda: outbox

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    async with engine.begin() as conn:  # wipe all rows so every test starts clean
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))


async def register(
    client: AsyncClient,
    email: str = "owner@example.com",
    password: str = "correct-horse-1",
    clinic_name: str = "Sunrise Clinic",
) -> dict[str, str]:
    """Signs up an owner; returns auth headers including X-Clinic-Id."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Dr. Owner",
            "email": email,
            "password": password,
            "clinic_name": clinic_name,
        },
    )
    assert response.status_code == 201, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    headers["X-Clinic-Id"] = me["memberships"][0]["clinic_id"]
    return headers


def bearer(response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
