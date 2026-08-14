from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import articles as article_repository
from app.web import public_context, templates

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]

SECTION_PRESENTATION = {
    "blog": {
        "label": "Blog",
        "eyebrow": "// build log",
        "heading": "Aprendizados, decisões e bugs honestos.",
        "intro": (
            "Notas sobre o que estou construindo — incluindo a parte em que a "
            "documentação parece simples até o primeiro erro às 2h da manhã."
        ),
        "route_prefix": "/blog",
    },
    "journal": {
        "label": "Diário de Engenharia",
        "eyebrow": "// diário de engenharia",
        "heading": "Decisões de engenharia, do problema ao sistema.",
        "intro": (
            "Registros técnicos sobre arquitetura, dados e operação dos sistemas "
            "que estou construindo."
        ),
        "route_prefix": "/journal",
    },
}


def _article_list(request: Request, db: Session, section: str) -> HTMLResponse:
    presentation = SECTION_PRESENTATION[section]
    return templates.TemplateResponse(
        request=request,
        name="public/blog.html",
        context=public_context(
            request,
            section,
            articles=article_repository.list_published_by_section(db, section),
            **presentation,
        ),
    )


def _article_detail(
    request: Request,
    db: Session,
    section: str,
    slug: str,
) -> HTMLResponse:
    presentation = SECTION_PRESENTATION[section]
    article = article_repository.get_published_by_slug(db, section, slug)
    if article is None:
        return templates.TemplateResponse(
            request=request,
            name="public/404.html",
            context=public_context(request, section),
            status_code=404,
        )
    return templates.TemplateResponse(
        request=request,
        name="public/post.html",
        context=public_context(
            request,
            section,
            article=article,
            **presentation,
        ),
    )


@router.get("/blog", response_class=HTMLResponse)
def blog(request: Request, db: DBSession) -> HTMLResponse:
    return _article_list(request, db, "blog")


@router.get("/blog/{slug}", response_class=HTMLResponse)
def blog_detail(request: Request, slug: str, db: DBSession) -> HTMLResponse:
    return _article_detail(request, db, "blog", slug)


@router.get("/journal", response_class=HTMLResponse)
def journal(request: Request, db: DBSession) -> HTMLResponse:
    return _article_list(request, db, "journal")


@router.get("/journal/{slug}", response_class=HTMLResponse)
def journal_detail(request: Request, slug: str, db: DBSession) -> HTMLResponse:
    return _article_detail(request, db, "journal", slug)
