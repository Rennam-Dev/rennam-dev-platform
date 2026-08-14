from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import BASE_DIR, settings
from app.core.http import SecurityHeadersMiddleware
from app.core.logging import configure_auth_logging
from app.routes import admin, admin_articles, articles, public


def create_app() -> FastAPI:
    configure_auth_logging()
    application = FastAPI(
        title="rennam.dev",
        description="Portfólio técnico e mini-CMS autoral.",
        version="0.3.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )
    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="rennam_session",
        max_age=60 * 60 * 8,
        same_site="lax",
        https_only=settings.session_cookie_secure,
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_host_list,
        www_redirect=False,
    )
    application.add_middleware(
        SecurityHeadersMiddleware,
        production=settings.is_production,
    )
    application.mount(
        "/static", StaticFiles(directory=BASE_DIR / "static"), name="static"
    )
    application.include_router(public.router)
    application.include_router(articles.router)
    application.include_router(admin.router)
    application.include_router(admin_articles.router)
    return application


app = create_app()
