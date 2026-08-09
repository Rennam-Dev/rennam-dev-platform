import json
import logging
import re
from base64 import b64decode, b64encode
from collections import Counter
from io import StringIO

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from httpx import Response
from itsdangerous import TimestampSigner
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app import main as main_module
from app.core import security as security_module
from app.core.config import DEFAULT_SESSION_SECRET, Settings, settings
from app.core.database import SessionLocal
from app.core.logging import AUTH_HANDLER_NAME, AUTH_LOGGER_NAME
from app.core.security import hash_password, require_admin
from app.main import app
from app.models import Project
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


def project_data(
    csrf_token: str,
    *,
    slug: str = "rennam-semantic-docs",
    title: str = "Rennam Semantic Docs",
    summary: str = "Busca semântica em documentos com fontes verificáveis.",
    visibility: str = "published",
) -> dict[str, str]:
    return {
        "csrf_token": csrf_token,
        "title": title,
        "slug": slug,
        "summary": summary,
        "status": "building",
        "visibility": visibility,
        "technologies": "Python, FastAPI, pgvector",
    }


def create_project(client, *, visibility: str = "published") -> int:
    form_page = client.get("/admin/projetos/novo")
    response = client.post(
        "/admin/projetos/novo",
        data=project_data(csrf_from(form_page), visibility=visibility),
        follow_redirects=False,
    )
    assert response.status_code == 303
    match = re.fullmatch(
        r"/admin/projetos/(\d+)/editar\?saved=1",
        response.headers["location"],
    )
    assert match
    return int(match.group(1))


PROTECTED_ADMIN_ROUTES = {
    ("GET", "/admin"),
    ("POST", "/admin/logout"),
    ("GET", "/admin/projetos/novo"),
    ("POST", "/admin/projetos/novo"),
    ("GET", "/admin/projetos/{project_id}/editar"),
    ("POST", "/admin/projetos/{project_id}/editar"),
    ("POST", "/admin/projetos/{project_id}/excluir"),
}

STAGING_ADMIN_USERNAME = "staging-admin"
STAGING_ADMIN_PASSWORD = "valid-staging-password"


def make_staging_app(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[FastAPI, Settings]:
    configured_settings = Settings(
        app_env="staging",
        database_url=(
            "postgresql+psycopg://staging:discardable@db/staging_portfolio"
        ),
        session_secret="0123456789abcdef" * 4,
        admin_username=STAGING_ADMIN_USERNAME,
        admin_password_hash=hash_password(STAGING_ADMIN_PASSWORD),
        site_url="https://staging.example",
        allowed_hosts="staging.example",
        _env_file=None,
    )
    monkeypatch.setattr(main_module, "settings", configured_settings)
    monkeypatch.setattr(security_module, "settings", configured_settings)
    monkeypatch.setattr(admin_routes, "settings", configured_settings)
    return main_module.create_app(), configured_settings


def test_all_protected_admin_routes_use_require_admin() -> None:
    routes_with_dependency = {
        (method, route.path)
        for route in admin_routes.router.routes
        if isinstance(route, APIRoute)
        and any(
            dependency.call is require_admin
            for dependency in route.dependant.dependencies
        )
        for method in route.methods
    }
    assert routes_with_dependency == PROTECTED_ADMIN_ROUTES


def test_protected_admin_routes_redirect_without_session(client):
    requests = [
        ("GET", "/admin"),
        ("POST", "/admin/logout"),
        ("GET", "/admin/projetos/novo"),
        ("POST", "/admin/projetos/novo"),
        ("GET", "/admin/projetos/999/editar"),
        ("POST", "/admin/projetos/999/editar"),
        ("POST", "/admin/projetos/999/excluir"),
    ]

    for method, path in requests:
        response = client.request(method, path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/admin/login"


def test_invalid_admin_session_does_not_authorize(client):
    client.cookies.set("rennam_session", "invalid-signed-session")
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


@pytest.mark.no_database
def test_default_signed_cookie_does_not_authorize_valid_staging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application, configured_settings = make_staging_app(monkeypatch)
    payload = b64encode(
        json.dumps({"admin": configured_settings.admin_username}).encode("utf-8")
    )
    forged_cookie = TimestampSigner(DEFAULT_SESSION_SECRET).sign(payload).decode()

    with TestClient(
        application,
        base_url="https://staging.example",
    ) as staging_client:
        response = staging_client.get(
            "/admin/projetos/novo",
            headers={"Cookie": f"rennam_session={forged_cookie}"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


@pytest.mark.no_database
def test_valid_staging_configuration_allows_legitimate_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application, configured_settings = make_staging_app(monkeypatch)

    with TestClient(
        application,
        base_url="https://staging.example",
    ) as staging_client:
        login_page = staging_client.get("/admin/login")
        response = staging_client.post(
            "/admin/login",
            data={
                "csrf_token": csrf_from(login_page),
                "username": configured_settings.admin_username,
                "password": STAGING_ADMIN_PASSWORD,
            },
            follow_redirects=False,
        )
        signed_session = response.cookies["rennam_session"]
        session_payload = json.loads(
            b64decode(
                TimestampSigner(configured_settings.session_secret).unsign(
                    signed_session
                )
            )
        )
        protected_page = staging_client.get("/admin/projetos/novo")

    assert login_page.status_code == 200
    assert "; secure" in login_page.headers["set-cookie"].lower()
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert session_payload["admin"] == configured_settings.admin_username
    assert protected_page.status_code == 200


def test_unauthenticated_request_does_not_reach_repository(client, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("repository should not be called")

    monkeypatch.setattr(admin_routes.project_repository, "list_all", fail_if_called)
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303


def test_login_is_public_without_redirect_loop_and_public_site_stays_public(client):
    login_page = client.get("/admin/login", follow_redirects=False)
    assert login_page.status_code == 200
    assert client.get("/", follow_redirects=False).status_code == 200


def test_authenticated_admin_routes_and_logout(client):
    login(client)

    dashboard = client.get("/admin")
    new_project = client.get("/admin/projetos/novo")
    assert dashboard.status_code == 200
    assert new_project.status_code == 200
    assert dashboard.headers["cache-control"] == "no-store"
    assert new_project.headers["cache-control"] == "no-store"

    logout_response = client.post(
        "/admin/logout",
        data={"csrf_token": csrf_from(dashboard)},
        follow_redirects=False,
    )
    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/admin/login"

    after_logout = client.get("/admin", follow_redirects=False)
    assert after_logout.status_code == 303
    assert after_logout.headers["location"] == "/admin/login"


def test_admin_can_create_project(client):
    login(client)
    create_page = client.get("/admin/projetos/novo")
    slug_input = re.search(r'<input name="slug"[^>]*>', create_page.text)
    assert slug_input
    assert "readonly" not in slug_input.group()
    create_project(client)

    public_page = client.get("/projetos/rennam-semantic-docs")
    assert public_page.status_code == 200
    assert "Rennam Semantic Docs" in public_page.text
    assert "pgvector" in public_page.text


def test_admin_can_update_project_while_preserving_slug(client):
    login(client)
    project_id = create_project(client)
    edit_page = client.get(f"/admin/projetos/{project_id}/editar")
    slug_input = re.search(r'<input name="slug"[^>]*>', edit_page.text)
    assert slug_input
    assert "readonly" in slug_input.group()
    assert "Imutável após a criação" in edit_page.text

    response = client.post(
        f"/admin/projetos/{project_id}/editar",
        data=project_data(
            csrf_from(edit_page),
            title="Rennam Semantic Docs atualizado",
            summary="Resumo atualizado sem alterar a URL pública original.",
        ),
        follow_redirects=False,
    )
    assert response.status_code == 303

    with SessionLocal() as db:
        project = db.get(Project, project_id)
        assert project is not None
        assert project.slug == "rennam-semantic-docs"
        assert project.title == "Rennam Semantic Docs atualizado"
        assert project.summary == (
            "Resumo atualizado sem alterar a URL pública original."
        )

    public_page = client.get("/projetos/rennam-semantic-docs")
    assert public_page.status_code == 200
    assert "Rennam Semantic Docs atualizado" in public_page.text


@pytest.mark.parametrize("visibility", ["draft", "published"])
def test_manual_slug_change_is_rejected_without_partial_update(client, visibility):
    login(client)
    project_id = create_project(client, visibility=visibility)
    edit_page = client.get(f"/admin/projetos/{project_id}/editar")

    response = client.post(
        f"/admin/projetos/{project_id}/editar",
        data=project_data(
            csrf_from(edit_page),
            slug="url-adulterada",
            title="Título não deve ser persistido",
            summary="Resumo não deve ser persistido após adulteração do slug.",
            visibility=visibility,
        ),
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "não pode ser alterado após a criação" in response.text

    with SessionLocal() as db:
        project = db.get(Project, project_id)
        assert project is not None
        assert project.slug == "rennam-semantic-docs"
        assert project.title == "Rennam Semantic Docs"
        assert project.summary == (
            "Busca semântica em documentos com fontes verificáveis."
        )

    expected_original_status = 200 if visibility == "published" else 404
    assert (
        client.get("/projetos/rennam-semantic-docs").status_code
        == expected_original_status
    )
    assert client.get("/projetos/url-adulterada").status_code == 404


def test_project_slug_remains_unique_on_creation(client):
    login(client)
    create_project(client)
    form_page = client.get("/admin/projetos/novo")

    response = client.post(
        "/admin/projetos/novo",
        data=project_data(
            csrf_from(form_page),
            title="Outro projeto",
            summary="Outro projeto tentando reutilizar uma URL já existente.",
        ),
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "já está sendo usado por outro projeto" in response.text


def test_project_edit_still_requires_csrf(client):
    login(client)
    project_id = create_project(client)
    response = client.post(
        f"/admin/projetos/{project_id}/editar",
        data=project_data(""),
        follow_redirects=False,
    )
    assert response.status_code == 403


@pytest.mark.parametrize("visibility", ["draft", "published"])
def test_manual_delete_is_blocked_and_project_is_preserved(
    client, caplog, visibility
):
    login(client)
    project_id = create_project(client, visibility=visibility)
    edit_page = client.get(f"/admin/projetos/{project_id}/editar")
    assert "/excluir" not in edit_page.text
    assert "Exclusão definitiva desabilitada" in edit_page.text
    assert "Arquivamento e restauração" in edit_page.text
    caplog.set_level(logging.WARNING, logger="rennam.admin_projects")

    response = client.post(
        f"/admin/projetos/{project_id}/excluir",
        data={"csrf_token": csrf_from(edit_page)},
        follow_redirects=False,
    )
    assert response.status_code == 409
    assert "Exclusão definitiva está desabilitada" in response.text

    with SessionLocal() as db:
        project = db.get(Project, project_id)
        assert project is not None
        assert project.slug == "rennam-semantic-docs"
        assert {technology.name for technology in project.technologies} == {
            "Python",
            "FastAPI",
            "pgvector",
        }

    expected_public_status = 200 if visibility == "published" else 404
    assert (
        client.get("/projetos/rennam-semantic-docs").status_code
        == expected_public_status
    )
    records = [
        record
        for record in caplog.records
        if record.name == "rennam.admin_projects"
    ]
    assert len(records) == 1
    assert records[0].event == "admin_project_delete_denied"
    assert records[0].project_id == project_id
    assert records[0].result == "denied"


def test_project_delete_requires_auth_and_preserves_project(client):
    login(client)
    project_id = create_project(client)
    edit_page = client.get(f"/admin/projetos/{project_id}/editar")
    csrf_token = csrf_from(edit_page)
    client.cookies.clear()

    response = client.post(
        f"/admin/projetos/{project_id}/excluir",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"
    with SessionLocal() as db:
        assert db.get(Project, project_id) is not None


def test_project_delete_requires_valid_csrf_and_preserves_project(client):
    login(client)
    project_id = create_project(client)
    response = client.post(
        f"/admin/projetos/{project_id}/excluir",
        data={"csrf_token": "invalid-csrf-token"},
        follow_redirects=False,
    )
    assert response.status_code == 403
    with SessionLocal() as db:
        assert db.get(Project, project_id) is not None


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


def test_different_remote_ips_do_not_share_the_limit() -> None:
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


def test_forwarded_headers_from_untrusted_origin_do_not_change_identity() -> None:
    proxy_guarded_app = ProxyHeadersMiddleware(
        app,
        trusted_hosts=settings.forwarded_allow_ips,
    )
    with TestClient(
        proxy_guarded_app,
        client=("192.0.2.30", 50000),
    ) as spoofing_client:
        login_page = spoofing_client.get("/admin/login")
        csrf_token = csrf_from(login_page)
        for attempt in range(settings.admin_login_max_failures):
            response = spoofing_client.post(
                "/admin/login",
                data={
                    "csrf_token": csrf_token,
                    "username": "rennam",
                    "password": "wrong-password",
                },
                headers={
                    "Forwarded": f"for=203.0.113.{attempt + 1}",
                    "X-Forwarded-For": f"203.0.113.{attempt + 1}",
                    "X-Forwarded-Proto": "https",
                    "X-Real-IP": f"198.51.100.{attempt + 1}",
                },
                follow_redirects=False,
            )
            assert response.status_code == 401

        limited = spoofing_client.post(
            "/admin/login",
            data={
                "csrf_token": csrf_token,
                "username": "rennam",
                "password": "test-password",
            },
            headers={
                "Forwarded": "for=203.0.113.250",
                "X-Forwarded-For": "203.0.113.250",
                "X-Forwarded-Proto": "https",
                "X-Real-IP": "198.51.100.250",
            },
            follow_redirects=False,
        )

    assert limited.status_code == 429


def test_rate_limiter_uses_ip_supplied_by_trusted_proxy() -> None:
    proxied_app = ProxyHeadersMiddleware(
        app,
        trusted_hosts="192.0.2.0/24",
    )
    forwarded_client = "203.0.113.10"
    other_forwarded_client = "198.51.100.20"
    with TestClient(
        proxied_app,
        client=("192.0.2.10", 50000),
    ) as proxy_client:
        csrf_token = csrf_from(proxy_client.get("/admin/login"))

        def attempt(password: str, forwarded_for: str) -> Response:
            return proxy_client.post(
                "/admin/login",
                data={
                    "csrf_token": csrf_token,
                    "username": "rennam",
                    "password": password,
                },
                headers={
                    "X-Forwarded-For": forwarded_for,
                    "X-Forwarded-Proto": "https",
                },
                follow_redirects=False,
            )

        for _ in range(settings.admin_login_max_failures):
            assert attempt("wrong-password", forwarded_client).status_code == 401

        assert attempt("test-password", forwarded_client).status_code == 429
        assert attempt("test-password", other_forwarded_client).status_code == 303


def test_login_audit_events_are_emitted_once_and_sanitized(client, monkeypatch):
    password = "never-log-this-password"
    session_cookie = client.get("/admin/login").cookies.get("rennam_session")
    logger = logging.getLogger(AUTH_LOGGER_NAME)
    handler = next(
        handler
        for handler in logger.handlers
        if handler.get_name() == AUTH_HANDLER_NAME
    )
    output_stream = StringIO()
    monkeypatch.setattr(handler, "stream", output_stream)

    assert login_attempt(client, password=password).status_code == 401
    assert login_attempt(client, password="test-password").status_code == 303

    client.cookies.clear()
    for _ in range(settings.admin_login_max_failures):
        assert login_attempt(client, password=password).status_code == 401
    assert login_attempt(client, password=password).status_code == 429

    lines = [
        line
        for line in output_stream.getvalue().splitlines()
        if f"logger={AUTH_LOGGER_NAME}" in line
    ]
    events = Counter(
        match.group(1)
        for line in lines
        if (match := re.search(r"\bevent=([^ ]+)", line))
    )

    assert events == {
        "admin_login_success": 1,
        "admin_login_failure": settings.admin_login_max_failures + 1,
        "admin_login_rate_limited": 1,
    }
    assert len(lines) == sum(events.values())
    assert all("level=INFO" in line for line in lines)
    assert all("path=/admin/login" in line for line in lines)

    output = "\n".join(lines)
    assert password not in output
    assert settings.admin_password_hash not in output
    assert settings.session_secret not in output
    assert settings.database_url not in output
    assert session_cookie not in output
    assert "rennam_session" not in output
    assert "csrf_token" not in output
    assert "authorization" not in output.lower()
