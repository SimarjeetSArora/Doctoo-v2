from httpx import AsyncClient

from tests.conftest import Outbox, bearer, register

API = "/api/v1"


async def test_register_creates_owner_of_new_clinic(client: AsyncClient) -> None:
    headers = await register(client, email="Owner@Example.com")

    me = (await client.get(f"{API}/auth/me", headers=headers)).json()
    assert me["user"]["email"] == "owner@example.com"  # stored lowercase
    assert me["memberships"] == [
        {"clinic_id": headers["X-Clinic-Id"], "clinic_name": "Sunrise Clinic", "role": "owner"}
    ]


async def test_register_rejects_duplicate_email_and_weak_password(client: AsyncClient) -> None:
    await register(client)
    dup = await client.post(
        f"{API}/auth/register",
        json={
            "full_name": "X Y",
            "email": "OWNER@example.com",
            "password": "another-pass-1",
            "clinic_name": "Other",
        },
    )
    assert dup.status_code == 409

    weak = await client.post(
        f"{API}/auth/register",
        json={
            "full_name": "X Y",
            "email": "new@example.com",
            "password": "short",
            "clinic_name": "C",
        },
    )
    assert weak.status_code == 422


async def test_login_success_and_failure(client: AsyncClient) -> None:
    await register(client)
    wrong = await client.post(
        f"{API}/auth/login", json={"email": "owner@example.com", "password": "nope-nope-1"}
    )
    unknown = await client.post(
        f"{API}/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-1"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # doesn't reveal which emails exist

    ok = await client.post(
        f"{API}/auth/login", json={"email": "OWNER@example.com", "password": "correct-horse-1"}
    )
    assert ok.status_code == 200
    assert (await client.get(f"{API}/auth/me", headers=bearer(ok))).status_code == 200


async def test_me_requires_valid_token(client: AsyncClient) -> None:
    assert (await client.get(f"{API}/auth/me")).status_code == 401
    bad = {"Authorization": "Bearer not-a-real-token"}
    assert (await client.get(f"{API}/auth/me", headers=bad)).status_code == 401


async def test_refresh_cookie_and_logout(client: AsyncClient) -> None:
    await register(client)  # sets the httpOnly refresh cookie on the client
    refreshed = await client.post(f"{API}/auth/refresh")
    assert refreshed.status_code == 200
    assert (await client.get(f"{API}/auth/me", headers=bearer(refreshed))).status_code == 200

    assert (await client.post(f"{API}/auth/logout")).status_code == 204
    assert (await client.post(f"{API}/auth/refresh")).status_code == 401


async def test_logout_all_revokes_every_session(client: AsyncClient) -> None:
    headers = await register(client)
    stolen_cookie = client.cookies.get("doctoo_refresh")

    assert (await client.post(f"{API}/auth/logout-all", headers=headers)).status_code == 204
    client.cookies.set("doctoo_refresh", stolen_cookie, path="/api/v1/auth")
    assert (await client.post(f"{API}/auth/refresh")).status_code == 401


async def test_password_reset_flow(client: AsyncClient, outbox: Outbox) -> None:
    await register(client)
    old_cookie = client.cookies.get("doctoo_refresh")

    # Unknown email gets the same response, and no email is sent.
    r = await client.post(f"{API}/auth/password/forgot", json={"email": "ghost@example.com"})
    assert r.status_code == 202 and outbox.messages == []

    await client.post(f"{API}/auth/password/forgot", json={"email": "owner@example.com"})
    assert outbox.last_link().startswith("http://localhost:5173/reset-password?token=")
    token = outbox.last_token()

    reset = await client.post(
        f"{API}/auth/password/reset", json={"token": token, "new_password": "brand-new-pass-2"}
    )
    assert reset.status_code == 200

    # Link works only once.
    again = await client.post(
        f"{API}/auth/password/reset", json={"token": token, "new_password": "brand-new-pass-3"}
    )
    assert again.status_code == 400

    # Old sessions are logged out; new password works, old one doesn't.
    client.cookies.set("doctoo_refresh", old_cookie, path="/api/v1/auth")
    assert (await client.post(f"{API}/auth/refresh")).status_code == 401
    login = f"{API}/auth/login"
    old = await client.post(
        login, json={"email": "owner@example.com", "password": "correct-horse-1"}
    )
    new = await client.post(
        login, json={"email": "owner@example.com", "password": "brand-new-pass-2"}
    )
    assert (old.status_code, new.status_code) == (401, 200)
