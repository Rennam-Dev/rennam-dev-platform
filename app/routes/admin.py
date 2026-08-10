import ipaddress
import logging
from collections.abc import Mapping
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import AUTH_LOGGER_NAME
from app.core.security import (
    ensure_csrf_token,
    is_admin,
    login_admin,
    logout_admin,
    require_admin,
    validate_csrf,
    verify_admin_credentials,
)
from app.repositories import projects as project_repository
from app.schemas.project import ProjectForm
from app.services import projects as project_service
from app.services.login_protection import LoginRateLimiter, RateLimitDecision
from app.web import templates

router = APIRouter(prefix="/admin")
DBSession = Annotated[Session, Depends(get_db)]
AdminAccess = Annotated[None, Depends(require_admin)]
logger = logging.getLogger(AUTH_LOGGER_NAME)
project_logger = logging.getLogger("rennam.admin_projects")
login_rate_limiter = LoginRateLimiter(
    max_failures=settings.admin_login_max_failures,
    window_seconds=settings.admin_login_window_seconds,
    max_clients=settings.admin_login_max_clients,
)


def redirect_to_login() -> RedirectResponse:
    return RedirectResponse("/admin/login", status_code=303)


def admin_context(request: Request, **extra) -> dict:
    return {
        "request": request,
        "settings": settings,
        "csrf_token": ensure_csrf_token(request),
        **extra,
    }


def observed_client_ip(request: Request) -> str:
    if request.client is None:
        return "unknown"
    try:
        return ipaddress.ip_address(request.client.host).compressed
    except ValueError:
        return "unknown"


def audit_login(event: str, request: Request, client_ip: str, result: str) -> None:
    logger.info(
        event,
        extra={
            "event": event,
            "client_ip": client_ip,
            "path": request.url.path,
            "result": result,
        },
    )


def rate_limited_response(
    request: Request, client_ip: str, decision: RateLimitDecision
) -> HTMLResponse:
    audit_login("admin_login_rate_limited", request, client_ip, "rate_limited")
    return templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context=admin_context(
            request,
            error="Muitas tentativas. Aguarde antes de tentar novamente.",
        ),
        status_code=429,
        headers={"Retry-After": str(decision.retry_after)},
    )


def form_values(project=None) -> dict[str, Any]:
    if project is None:
        return {
            "title": "",
            "slug": "",
            "summary": "",
            "problem": "",
            "solution": "",
            "architecture": "",
            "decisions": "",
            "results": "",
            "learnings": "",
            "course": "",
            "status": "planned",
            "visibility": "draft",
            "featured": False,
            "technologies": "",
            "repo_url": "",
            "demo_url": "",
            "cover_image_url": "",
            "seo_description": "",
        }
    values = {
        column.name: getattr(project, column.name)
        for column in project.__table__.columns
        if column.name not in {"id", "created_at", "updated_at"}
    }
    values["technologies"] = ", ".join(
        technology.name for technology in project.technologies
    )
    return values


def validate_project_form(
    raw: Mapping[str, object],
) -> tuple[ProjectForm | None, dict[str, object], list[str]]:
    values = ProjectForm.values_from_mapping(raw)
    try:
        return ProjectForm.from_mapping(raw), values, []
    except ValidationError as error:
        messages = [
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors()
        ]
        return None, values, messages


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_admin(request):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context=admin_context(request, error=None),
    )


@router.post("/login", response_class=HTMLResponse)
async def login(request: Request):
    data = await request.form()
    validate_csrf(request, str(data.get("csrf_token", "")))
    client_ip = observed_client_ip(request)
    try:
        decision = login_rate_limiter.check(client_ip)
    except Exception:
        decision = RateLimitDecision(
            limited=True,
            retry_after=settings.admin_login_window_seconds,
        )
    if decision.limited:
        return rate_limited_response(request, client_ip, decision)

    username = str(data.get("username", ""))
    password = str(data.get("password", ""))
    if verify_admin_credentials(username, password):
        login_rate_limiter.record_success(client_ip)
        login_admin(request)
        audit_login("admin_login_success", request, client_ip, "success")
        return RedirectResponse("/admin", status_code=303)
    login_rate_limiter.record_failure(client_ip)
    audit_login("admin_login_failure", request, client_ip, "failure")
    return templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context=admin_context(
            request,
            error=(
                "Configure ADMIN_PASSWORD_HASH no .env."
                if not settings.admin_password_hash
                else "Usuário ou senha inválidos."
            ),
        ),
        status_code=401,
    )


@router.post("/logout")
async def logout(request: Request, _admin: AdminAccess):
    data = await request.form()
    validate_csrf(request, str(data.get("csrf_token", "")))
    logout_admin(request)
    return redirect_to_login()


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, _admin: AdminAccess, db: DBSession):
    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context=admin_context(
            request,
            projects=project_repository.list_all(db),
        ),
    )


@router.get("/projetos/novo", response_class=HTMLResponse)
def new_project_page(request: Request, _admin: AdminAccess):
    return templates.TemplateResponse(
        request=request,
        name="admin/project_form.html",
        context=admin_context(
            request,
            page_title="Novo projeto",
            action="/admin/projetos/novo",
            values=form_values(),
            errors=[],
        ),
    )


@router.post("/projetos/novo", response_class=HTMLResponse)
async def create_project(request: Request, _admin: AdminAccess, db: DBSession):
    data = await request.form()
    validate_csrf(request, str(data.get("csrf_token", "")))
    form, values, errors = validate_project_form(data)
    if form and project_repository.get_by_slug(db, form.slug):
        errors.append("slug: já está sendo usado por outro projeto.")
        form = None
    if form:
        try:
            project = project_service.create_project(db, form)
            return RedirectResponse(
                f"/admin/projetos/{project.id}/editar?saved=1", status_code=303
            )
        except IntegrityError:
            db.rollback()
            errors.append("Não foi possível salvar: valor único duplicado.")
    return templates.TemplateResponse(
        request=request,
        name="admin/project_form.html",
        context=admin_context(
            request,
            page_title="Novo projeto",
            action="/admin/projetos/novo",
            values=values,
            errors=errors,
        ),
        status_code=422,
    )


@router.get("/projetos/{project_id}/editar", response_class=HTMLResponse)
def edit_project_page(
    request: Request,
    _admin: AdminAccess,
    project_id: int,
    db: DBSession,
    saved: int = 0,
):
    project = project_repository.get_by_id(db, project_id)
    if project is None:
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="admin/project_form.html",
        context=admin_context(
            request,
            page_title=f"Editar: {project.title}",
            action=f"/admin/projetos/{project.id}/editar",
            values=form_values(project),
            errors=[],
            saved=bool(saved),
            project=project,
        ),
    )


@router.post("/projetos/{project_id}/editar", response_class=HTMLResponse)
async def update_project(
    request: Request,
    _admin: AdminAccess,
    project_id: int,
    db: DBSession,
):
    data = await request.form()
    validate_csrf(request, str(data.get("csrf_token", "")))
    project = project_repository.get_by_id(db, project_id)
    if project is None:
        return RedirectResponse("/admin", status_code=303)
    form, values, errors = validate_project_form(data)
    if form:
        try:
            project_service.update_project(db, project, form)
            return RedirectResponse(
                f"/admin/projetos/{project.id}/editar?saved=1", status_code=303
            )
        except project_service.ProjectSlugImmutableError as error:
            errors.append(str(error))
            values["slug"] = project.slug
        except IntegrityError:
            db.rollback()
            errors.append("Não foi possível salvar: valor único duplicado.")
    return templates.TemplateResponse(
        request=request,
        name="admin/project_form.html",
        context=admin_context(
            request,
            page_title=f"Editar: {project.title}",
            action=f"/admin/projetos/{project.id}/editar",
            values=values,
            errors=errors,
            project=project,
        ),
        status_code=422,
    )


@router.post("/projetos/{project_id}/excluir")
async def remove_project(
    request: Request,
    _admin: AdminAccess,
    project_id: int,
    db: DBSession,
):
    data = await request.form()
    validate_csrf(request, str(data.get("csrf_token", "")))
    project = project_repository.get_by_id(db, project_id)
    if project is None:
        return RedirectResponse("/admin", status_code=303)
    try:
        project_service.delete_project(db, project)
    except project_service.ProjectDeletionDisabledError as error:
        project_logger.warning(
            "admin_project_delete_denied",
            extra={
                "event": "admin_project_delete_denied",
                "project_id": project.id,
                "path": request.url.path,
                "result": "denied",
            },
        )
        return templates.TemplateResponse(
            request=request,
            name="admin/project_form.html",
            context=admin_context(
                request,
                page_title=f"Editar: {project.title}",
                action=f"/admin/projetos/{project.id}/editar",
                values=form_values(project),
                errors=[str(error)],
                project=project,
            ),
            status_code=409,
        )
