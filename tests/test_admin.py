import logging
import re

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.routes import admin as admin_routes


def csrf_from(response) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match
    return match.group(1)


def login(client):
    login_page = client.get("/admin/login")
    response = client.post(
        "/admin/login",
        data={
            "csrf_token": csrf_from(login_page),
            "username": "rennam",
            "password": "test-password",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def login_attempt(client, *, password: str, username: str = "rennam"):
    login_page = client.get("/admin/login")
    return client.post(
        "/admin/login",
        data={
            "csrf_token": csrf_from(login_page),
            "username": username,
            "password": password,
        },
        follow_redirects=False,
    )


def test_admin_requires_login(client):
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_admin_can_create_project(client):
    login(client)
    form_page = client.get("/admin/projetos/novo")
    response = client.post(
        "/admin/projetos/novo",
        data={
            "csrf_token": csrf_from(form_page),
            "title": "Rennam Semantic Docs",
            "slug": "rennam-semantic-docs",
            "summary": "Busca semântica em documentos com fontes verificáveis.",
            "status": "building",
            "visibility": "published",
            "featured": "on",
            "technologies": "Python, FastAPI, pgvector",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    public_page = client.get("/projetos/rennam-semantic-docs")
    assert public_page.status_code == 200
    assert "Rennam Semantic Docs" in public_page.text
    assert "pgvector" in public_page.text


def test_csrf_is_required(client):
    login(client)
    response = client.post(
        "/admin/projetos/novo",
        data={
            "title": "Sem CSRF",
            "slug": "sem-csrf",
            "summary": "Esta requisição deve ser recusada pelo servidor.",
        },
    )
    assert response.status_code == 403


def test_invalid_logins_are_limited_before_argon2(client, monkeypatch):
    calls = 0
    original_verify = admin_routes.verify_admin_credentials

    def counted_verify(username: str, password: str) -> bool:
        nonlocal calls
        calls += 1
        return original_verify(username, password)

    monkeypatch.setattr(admin_routes, "verify_admin_credentials", counted_verify)

    for _ in range(settings.admin_login_max_failures):
        response = login_attempt(client, password="wrong-password")
        assert response.status_code == 401

    response = login_attempt(client, password="test-password")
    assert response.status_code == 429
    assert response.headers["retry-after"] == str(
        settings.admin_login_window_seconds
    )
    assert calls == settings.admin_login_max_failures


def test_valid_login_outside_block_and_success_resets_failures(client):
    for _ in range(settings.admin_login_max_failures - 1):
        assert login_attempt(client, password="wrong-password").status_code == 401

    assert login_attempt(client, password="test-password").status_code == 303

    logout_page = client.get("/admin")
    logout = client.post(
        "/admin/logout",
        data={"csrf_token": csrf_from(logout_page)},
        follow_redirects=False,
    )
    assert logout.status_code == 303

    for _ in range(settings.admin_login_max_failures - 1):
        assert login_attempt(client, password="wrong-password").status_code == 401


def test_different_remote_ips_do_not_share_the_limit():
    with (
        TestClient(app, client=("192.0.2.10", 50000)) as first_client,
        TestClient(app, client=("198.51.100.20", 50001)) as second_client,
    ):
        for _ in range(settings.admin_login_max_failures):
            assert (
                login_attempt(first_client, password="wrong-password").status_code
                == 401
            )

        assert login_attempt(first_client, password="test-password").status_code == 429
        assert (
            login_attempt(second_client, password="test-password").status_code == 303
        )


def test_login_audit_events_are_sanitized(client, caplog):
    password = "never-log-this-password"
    session_cookie = client.get("/admin/login").cookies.get("rennam_session")
    caplog.set_level(logging.INFO, logger="rennam.admin_auth")

    assert login_attempt(client, password=password).status_code == 401
    assert login_attempt(client, password="test-password").status_code == 303

    client.cookies.clear()
    for _ in range(settings.admin_login_max_failures):
        assert login_attempt(client, password=password).status_code == 401
    assert login_attempt(client, password=password).status_code == 429

    records = [
        record
        for record in caplog.records
        if record.name == "rennam.admin_auth"
    ]
    assert {record.event for record in records} == {
        "admin_login_success",
        "admin_login_failure",
        "admin_login_rate_limited",
    }
    serialized_records = " ".join(
        f"{record.getMessage()} {record.__dict__!r}" for record in records
    )
    assert password not in serialized_records
    assert settings.admin_password_hash not in serialized_records
    assert session_cookie not in serialized_records
    assert "rennam_session" not in serialized_records
    assert "csrf_token" not in serialized_records
