from collections.abc import Mapping
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_admin, validate_csrf
from app.models import Article
from app.repositories import articles as article_repository
from app.schemas.article import ArticleForm, CategoryForm
from app.services import articles as article_service
from app.web import templates

from .admin import admin_context

router = APIRouter(prefix="/admin")
DBSession = Annotated[Session, Depends(get_db)]
AdminAccess = Annotated[None, Depends(require_admin)]


def article_form_values(article: Article | None = None) -> dict[str, object]:
    if article is None:
        return {
            "title": "",
            "slug": "",
            "summary": "",
            "content_markdown": "",
            "section": "blog",
            "category_id": None,
            "tags": "",
        }
    return {
        "title": article.title,
        "slug": article.slug,
        "summary": article.summary,
        "content_markdown": article.content_markdown,
        "section": article.section,
        "category_id": article.category_id,
        "tags": ", ".join(tag.name for tag in article.tags),
    }


def validation_messages(error: ValidationError) -> list[str]:
    messages: list[str] = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "form"
        messages.append(f"{location}: {item['msg']}")
    return messages


def validate_article_form(
    raw: Mapping[str, object],
) -> tuple[ArticleForm | None, dict[str, object], list[str]]:
    values = ArticleForm.values_from_mapping(raw)
    try:
        return ArticleForm.from_mapping(raw), values, []
    except ValidationError as error:
        return None, values, validation_messages(error)


def validate_category_form(
    raw: Mapping[str, object],
) -> tuple[CategoryForm | None, dict[str, object], list[str]]:
    values = {"name": raw.get("name", "")}
    try:
        return CategoryForm.from_mapping(raw), values, []
    except ValidationError as error:
        return None, values, validation_messages(error)


def article_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Artigo não encontrado.",
    )


def article_form_response(
    request: Request,
    db: Session,
    *,
    page_title: str,
    action: str,
    values: dict[str, object],
    errors: list[str],
    article: Article | None = None,
    saved: bool = False,
    published: bool = False,
    unpublished: bool = False,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="admin/article_form.html",
        context=admin_context(
            request,
            page_title=page_title,
            action=action,
            values=values,
            errors=errors,
            categories=article_repository.list_categories(db),
            article=article,
            saved=saved,
            published=published,
            unpublished=unpublished,
        ),
        status_code=status_code,
    )


@router.get("/artigos", response_class=HTMLResponse)
def list_articles(request: Request, _admin: AdminAccess, db: DBSession):
    return templates.TemplateResponse(
        request=request,
        name="admin/articles.html",
        context=admin_context(
            request,
            articles=article_repository.list_all(db),
        ),
    )


@router.get("/artigos/novo", response_class=HTMLResponse)
def new_article_page(request: Request, _admin: AdminAccess, db: DBSession):
    return article_form_response(
        request,
        db,
        page_title="Novo artigo",
        action="/admin/artigos/novo",
        values=article_form_values(),
        errors=[],
    )


@router.post("/artigos/novo", response_class=HTMLResponse)
async def create_article(request: Request, _admin: AdminAccess, db: DBSession):
    data = await request.form()
    validate_csrf(request, str(data.get("csrf_token", "")))
    form, values, errors = validate_article_form(data)
    if form:
        try:
            article = article_service.create_article(db, form)
            return RedirectResponse(
                f"/admin/artigos/{article.id}/editar?saved=1",
                status_code=303,
            )
        except (
            article_service.ArticleCategoryError,
            article_service.ArticleConflictError,
            article_service.ArticleTagError,
        ) as error:
            errors.append(str(error))
    return article_form_response(
        request,
        db,
        page_title="Novo artigo",
        action="/admin/artigos/novo",
        values=values,
        errors=errors,
        status_code=422,
    )


@router.get("/artigos/{article_id}/editar", response_class=HTMLResponse)
def edit_article_page(
    request: Request,
    _admin: AdminAccess,
    article_id: int,
    db: DBSession,
    saved: int = 0,
    published: int = 0,
    unpublished: int = 0,
):
    article = article_repository.get_by_id(db, article_id)
    if article is None:
        raise article_not_found()
    return article_form_response(
        request,
        db,
        page_title=f"Editar: {article.title}",
        action=f"/admin/artigos/{article.id}/editar",
        values=article_form_values(article),
        errors=[],
        article=article,
        saved=bool(saved),
        published=bool(published),
        unpublished=bool(unpublished),
    )


@router.post("/artigos/{article_id}/editar", response_class=HTMLResponse)
async def update_article(
    request: Request,
    _admin: AdminAccess,
    article_id: int,
    db: DBSession,
):
    data = await request.form()
    validate_csrf(request, str(data.get("csrf_token", "")))
    article = article_repository.get_by_id(db, article_id)
    if article is None:
        raise article_not_found()
    form, values, errors = validate_article_form(data)
    if form:
        try:
            article_service.update_article(db, article, form)
            return RedirectResponse(
                f"/admin/artigos/{article.id}/editar?saved=1",
                status_code=303,
            )
        except (
            article_service.ArticleCategoryError,
            article_service.ArticleConflictError,
            article_service.ArticleTagError,
            article_service.ArticlePublicationError,
            article_service.ArticleUrlImmutableError,
        ) as error:
            errors.append(str(error))
    return article_form_response(
        request,
        db,
        page_title=f"Editar: {article.title}",
        action=f"/admin/artigos/{article.id}/editar",
        values=values,
        errors=errors,
        article=article,
        status_code=422,
    )


@router.get("/artigos/{article_id}/preview", response_class=HTMLResponse)
def preview_article(
    request: Request,
    _admin: AdminAccess,
    article_id: int,
    db: DBSession,
):
    article = article_repository.get_by_id(db, article_id)
    if article is None:
        raise article_not_found()
    return templates.TemplateResponse(
        request=request,
        name="admin/article_preview.html",
        context=admin_context(request, article=article),
    )


@router.post("/artigos/{article_id}/publicar", response_class=HTMLResponse)
async def publish_article(
    request: Request,
    _admin: AdminAccess,
    article_id: int,
    db: DBSession,
):
    data = await request.form()
    validate_csrf(request, str(data.get("csrf_token", "")))
    article = article_repository.get_by_id(db, article_id)
    if article is None:
        raise article_not_found()
    try:
        article_service.publish_article(db, article)
    except article_service.ArticlePublicationError as error:
        return article_form_response(
            request,
            db,
            page_title=f"Editar: {article.title}",
            action=f"/admin/artigos/{article.id}/editar",
            values=article_form_values(article),
            errors=[str(error)],
            article=article,
            status_code=422,
        )
    return RedirectResponse(
        f"/admin/artigos/{article.id}/editar?published=1",
        status_code=303,
    )


@router.post("/artigos/{article_id}/despublicar", response_class=HTMLResponse)
async def unpublish_article(
    request: Request,
    _admin: AdminAccess,
    article_id: int,
    db: DBSession,
):
    data = await request.form()
    validate_csrf(request, str(data.get("csrf_token", "")))
    article = article_repository.get_by_id(db, article_id)
    if article is None:
        raise article_not_found()
    try:
        article_service.unpublish_article(db, article)
    except article_service.ArticlePublicationError as error:
        return article_form_response(
            request,
            db,
            page_title=f"Editar: {article.title}",
            action=f"/admin/artigos/{article.id}/editar",
            values=article_form_values(article),
            errors=[str(error)],
            article=article,
            status_code=422,
        )
    return RedirectResponse(
        f"/admin/artigos/{article.id}/editar?unpublished=1",
        status_code=303,
    )


@router.get("/categorias", response_class=HTMLResponse)
def list_categories(
    request: Request,
    _admin: AdminAccess,
    db: DBSession,
    saved: int = 0,
):
    return templates.TemplateResponse(
        request=request,
        name="admin/categories.html",
        context=admin_context(
            request,
            categories=article_repository.list_categories(db),
            values={"name": ""},
            errors=[],
            saved=bool(saved),
        ),
    )


@router.post("/categorias/nova", response_class=HTMLResponse)
async def create_category(request: Request, _admin: AdminAccess, db: DBSession):
    data = await request.form()
    validate_csrf(request, str(data.get("csrf_token", "")))
    form, values, errors = validate_category_form(data)
    if form:
        try:
            article_service.create_category(db, form)
            return RedirectResponse("/admin/categorias?saved=1", status_code=303)
        except (
            article_service.CategoryConflictError,
            article_service.CategoryError,
        ) as error:
            errors.append(str(error))
    return templates.TemplateResponse(
        request=request,
        name="admin/categories.html",
        context=admin_context(
            request,
            categories=article_repository.list_categories(db),
            values=values,
            errors=errors,
            saved=False,
        ),
        status_code=422,
    )
