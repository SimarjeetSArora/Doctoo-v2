"""Shared test setup: a separate `doctoo_test` database and captured emails."""

import itertools
import re
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
from app.services.sms import get_sms_sender
from app.services.whatsapp import get_whatsapp_sender

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

    def last_code(self) -> str:
        """The 6-digit code in the most recent email."""
        return re.search(r"\b(\d{6})\b", self.messages[-1].body).group(1)


class PhoneOutbox:
    """Collects SMS or WhatsApp messages instead of sending them."""

    def __init__(self) -> None:
        self.messages: list = []

    async def send(self, message) -> None:
        self.messages.append(message)

    def last_code(self) -> str:
        return re.search(r"\b(\d{6})\b", self.messages[-1].render()).group(1)

    def last_token(self) -> str:
        return re.search(r"token=(\S+)", self.messages[-1].render()).group(1)


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
def sms_outbox() -> PhoneOutbox:
    return PhoneOutbox()


@pytest.fixture
def whatsapp_outbox() -> PhoneOutbox:
    return PhoneOutbox()


@pytest.fixture
async def client(
    engine: AsyncEngine, outbox: Outbox, sms_outbox: PhoneOutbox, whatsapp_outbox: PhoneOutbox
) -> AsyncIterator[AsyncClient]:
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_email_sender] = lambda: outbox
    app.dependency_overrides[get_sms_sender] = lambda: sms_outbox
    app.dependency_overrides[get_whatsapp_sender] = lambda: whatsapp_outbox

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    async with engine.begin() as conn:  # wipe all rows so every test starts clean
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))


_phone_numbers = itertools.count(1)


def unique_phone() -> str:
    """A different valid Indian mobile number each call (phone numbers are unique per user)."""
    return f"+9198{next(_phone_numbers):08d}"


PROFILE = {
    "salutation": "Dr.",
    "first_name": "Owner",
    "middle_name": "",
    "last_name": "Person",
}


async def register(
    client: AsyncClient,
    email: str = "owner@example.com",
    password: str = "correct-horse-1",
    clinic_name: str = "Sunrise Clinic",
    **profile: str,
) -> dict[str, str]:
    """Signs up an owner (requesting and entering the emailed code); returns auth headers
    including X-Clinic-Id."""
    sent = await client.post(
        "/api/v1/auth/otp", json={"channel": "email", "target": email, "purpose": "register"}
    )
    assert sent.status_code == 200, sent.text
    outbox = app.dependency_overrides[get_email_sender]()
    response = await client.post(
        "/api/v1/auth/register",
        json={
            **PROFILE,
            "phone": unique_phone(),
            **profile,
            "email": email,
            "email_code": outbox.last_code(),
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


# Older tests refer to SmsOutbox.
SmsOutbox = PhoneOutbox
