import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app import main as main_module
from app.core.config import MIN_SESSION_SECRET_LENGTH, AppEnvironment, Settings

pytestmark = pytest.mark.no_database

EXPECTED_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; base-uri 'none'; object-src 'none'; "
    "frame-ancestors 'none'; form-action 'self'; script-src 'none'; "
    "style-src 'self'; img-src 'self'; font-src 'self'; "
    "frame-src 'none'; worker-src 'none'"
)
EXPECTED_PERMISSIONS_POLICY = (
    "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
)
EXPECTED_HSTS_POLICY = "max-age=31536000"

VALID_ARGON2_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$ZGlnZXN0"


def make_app(
    monkeypatch: pytest.MonkeyPatch,
    configured_settings: Settings,
) -> FastAPI:
    monkeypatch.setattr(main_module, "settings", configured_settings)
    return main_module.create_app()


def production_settings() -> Settings:
    return Settings(
        app_env="production",
        database_url="postgresql+psycopg://app:discardable@db/rennam_dev",
        session_secret="s" * MIN_SESSION_SECRET_LENGTH,
        admin_username="admin",
        admin_password_hash=VALID_ARGON2_HASH,
        site_url="https://rennam.example",
        allowed_hosts="rennam.example",
        _env_file=None,
    )


def assert_security_headers(response: Response) -> None:
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == (
        "strict-origin-when-cross-origin"
    )
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["permissions-policy"] == EXPECTED_PERMISSIONS_POLICY
    assert response.headers["content-security-policy"] == (
        EXPECTED_CONTENT_SECURITY_POLICY
    )
    assert "unsafe-inline" not in response.headers["content-security-policy"]
    assert "unsafe-eval" not in response.headers["content-security-policy"]


@pytest.mark.parametrize("app_env", ["development", "test", "staging"])
def test_non_production_exposes_docs_and_openapi_without_hsts(
    monkeypatch: pytest.MonkeyPatch,
    app_env: AppEnvironment,
) -> None:
    application = make_app(
        monkeypatch,
        Settings(
            app_env=app_env,
            allowed_hosts="testserver",
            _env_file=None,
        ),
    )
    with TestClient(application) as client:
        docs = client.get("/docs")
        openapi = client.get("/openapi.json")
        public_page = client.get("/sobre")

    assert docs.status_code == 200
    assert "content-security-policy" not in docs.headers
    assert openapi.status_code == 200
    assert openapi.json()["info"]["title"] == "rennam.dev"
    assert public_page.status_code == 200
    assert "strict-transport-security" not in public_page.headers


def test_production_hides_all_openapi_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = make_app(monkeypatch, production_settings())
    with TestClient(
        application,
        base_url="https://rennam.example",
    ) as client:
        responses = {
            path: client.get(path)
            for path in ("/docs", "/redoc", "/openapi.json")
        }

    assert {path: response.status_code for path, response in responses.items()} == {
        "/docs": 404,
        "/redoc": 404,
        "/openapi.json": 404,
    }


def test_application_html_receives_security_headers_without_test_hsts(
    client: TestClient,
) -> None:
    public_page = client.get("/sobre")
    admin_login = client.get("/admin/login")

    assert public_page.status_code == 200
    assert_security_headers(public_page)
    assert_security_headers(admin_login)
    assert "strict-transport-security" not in public_page.headers
    assert "strict-transport-security" not in admin_login.headers
    assert admin_login.headers["cache-control"] == "no-store"


def test_production_adds_hsts_without_https_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = make_app(monkeypatch, production_settings())
    with TestClient(
        application,
        base_url="https://rennam.example",
    ) as client:
        response = client.get(
            "/sobre",
            headers={"X-Forwarded-Proto": "http"},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert response.headers["strict-transport-security"] == EXPECTED_HSTS_POLICY
    assert "location" not in response.headers
    assert_security_headers(response)


def test_production_plain_http_has_no_hsts_or_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = make_app(monkeypatch, production_settings())
    with TestClient(
        application,
        base_url="http://rennam.example",
    ) as client:
        response = client.get("/sobre", follow_redirects=False)

    assert response.status_code == 200
    assert "strict-transport-security" not in response.headers
    assert "location" not in response.headers


def test_trusted_proxy_alone_can_report_external_https(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = ProxyHeadersMiddleware(
        make_app(monkeypatch, production_settings()),
        trusted_hosts="192.0.2.0/24",
    )
    with TestClient(
        application,
        client=("192.0.2.10", 50000),
        base_url="http://rennam.example",
    ) as trusted_proxy:
        trusted_response = trusted_proxy.get(
            "/sobre",
            headers={"X-Forwarded-Proto": "https"},
        )
    with TestClient(
        application,
        client=("198.51.100.10", 50000),
        base_url="http://rennam.example",
    ) as untrusted_client:
        untrusted_response = untrusted_client.get(
            "/sobre",
            headers={"X-Forwarded-Proto": "https"},
        )

    assert trusted_response.status_code == 200
    assert (
        trusted_response.headers["strict-transport-security"]
        == EXPECTED_HSTS_POLICY
    )
    assert untrusted_response.status_code == 200
    assert "strict-transport-security" not in untrusted_response.headers


def test_unknown_host_is_rejected(client: TestClient) -> None:
    response = client.get("/sobre", headers={"Host": "attacker.example"})
    assert response.status_code == 400


def test_static_css_is_served_with_nosniff(client: TestClient) -> None:
    response = client.get("/static/css/app.css")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert response.headers["x-content-type-options"] == "nosniff"
