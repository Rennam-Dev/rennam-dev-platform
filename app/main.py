from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import BASE_DIR, settings
from app.routes import admin, public


def create_app() -> FastAPI:
    if settings.is_production and settings.uses_insecure_session_secret:
        raise RuntimeError("Defina SESSION_SECRET antes de iniciar em produção.")

    application = FastAPI(
        title="rennam.dev",
        description="Portfólio técnico e mini-CMS autoral.",
        version="0.2.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
    )
    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="rennam_session",
        max_age=60 * 60 * 8,
        same_site="lax",
        https_only=settings.is_production,
    )
    application.mount(
        "/static", StaticFiles(directory=BASE_DIR / "static"), name="static"
    )
    application.include_router(public.router)
    application.include_router(admin.router)
    return application


app = create_app()
